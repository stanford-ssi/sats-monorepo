#!/usr/bin/env python3
"""
send_cmd.py - interactively poke values into the slate over usb.

Field offsets come from the firmware ELF's debug info rather than from a
hardcoded table, so the offset always matches the binary that is actually
flashed. Values are encoded as a SatCmd, cobs framed and written to the
pico's cdc port, which is what CmdReceiver on the other end is expecting.

Usage:
    uv run scripts/send_cmd.py                          # sleep_ms, autodetected port
    uv run scripts/send_cmd.py --field temperature
    uv run scripts/send_cmd.py --port /dev/ttyACM0
    uv run scripts/send_cmd.py --dry-run                # print frames, send nothing
"""

import argparse
import struct
import sys

import serial
from serial.tools import list_ports

from parse_slate import get_struct_layout

DEFAULT_ELF = "bazel-bin/blink"
DEFAULT_STRUCT = "Slate"
DEFAULT_FIELD = "sleep_ms"

RASPBERRY_PI_VID = 0x2E8A

# CmdReceiver writes exactly one 32 bit word per command.
WORD_SIZE = 4


def varint(n: int) -> bytes:
    """Protobuf base 128 varint."""
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        out.append(byte | (0x80 if n else 0))
        if not n:
            return bytes(out)


def encode_cmd(offset: int, value: int) -> bytes:
    """A SatCmd on the wire, tag 1 = offset, tag 2 = value.

    Both fields are always written out, even when zero. Proto3 would normally
    leave a zero field off entirely, and an all zero SatCmd would then encode
    to nothing at all, which the receiver throws away as an empty frame.
    """
    return b"\x08" + varint(offset) + b"\x10" + varint(value)


def cobs_encode(data: bytes) -> bytes:
    """Cobs frame `data`, not including the trailing zero delimiter.

    Mirrors common/cobs/cobs.cpp: the payload is split into blocks of up to
    254 non zero bytes, each prefixed by a code byte holding the block length
    with the code byte included. A code of 0xff means the block was cut short
    by the length limit rather than by a zero, so no zero is restored there.
    """
    out = bytearray()
    block = bytearray()
    block_full = False  # the last block ended on the 254 byte limit, not a zero

    for byte in data:
        if byte == 0:
            out.append(len(block) + 1)
            out += block
            block.clear()
            block_full = False
        else:
            block.append(byte)
            block_full = len(block) == 254
            if block_full:
                out.append(0xFF)
                out += block
                block.clear()

    if not block_full:
        out.append(len(block) + 1)
        out += block
    return bytes(out)


def frame(offset: int, value: int) -> bytes:
    """The complete byte sequence to push down the wire for one command."""
    return cobs_encode(encode_cmd(offset, value)) + b"\x00"


def writable_fields(layout: dict) -> dict:
    """Fields the firmware can actually poke: single 32 bit words."""
    return {
        name: info for name, info in layout.items() if info["size"] == WORD_SIZE
    }


def parse_value(text: str, type_name: str) -> int:
    """Turn typed input into the 32 bits to drop at the offset.

    Floats are sent as their raw bit pattern, which is what the firmware's
    reinterpret_cast of the slate pointer expects to find there.
    """
    if "float" in type_name:
        return struct.unpack("<I", struct.pack("<f", float(text)))[0]

    value = int(text, 0)  # 0 base, so 0x20 and 0b101 work too
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"{value} does not fit in a uint32")
    return value


def autodetect_port() -> str:
    ports = [p for p in list_ports.comports() if p.vid == RASPBERRY_PI_VID]
    if not ports:
        raise SystemExit(
            "error: no raspberry pi usb device found, pass --port explicitly"
        )
    if len(ports) > 1:
        found = ", ".join(p.device for p in ports)
        raise SystemExit(f"error: several candidates ({found}), pass --port")
    return ports[0].device


def print_layout(struct_name: str, fields: dict, skipped: dict) -> None:
    print(f"struct {struct_name}:")
    for name, info in fields.items():
        print(f"  {name:<16} offset {info['offset']:>3}  {info['type']}")
    for name, info in skipped.items():
        print(f"  {name:<16} offset {info['offset']:>3}  {info['type']}  (not a word, skipped)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--elf", default=DEFAULT_ELF, help=f"firmware elf (default {DEFAULT_ELF})")
    parser.add_argument("--struct", default=DEFAULT_STRUCT, dest="struct_name")
    parser.add_argument("--field", default=DEFAULT_FIELD, help=f"field to start on (default {DEFAULT_FIELD})")
    parser.add_argument("--port", help="serial port (autodetected if omitted)")
    parser.add_argument("--dry-run", action="store_true", help="print the frames instead of sending them")
    args = parser.parse_args()

    try:
        layout = get_struct_layout(args.elf, args.struct_name)
    except (FileNotFoundError, ValueError) as err:
        raise SystemExit(f"error: {err}")

    fields = writable_fields(layout)
    if not fields:
        raise SystemExit(f"error: {args.struct_name} has no 4 byte fields to write")

    field = args.field
    if field not in fields:
        raise SystemExit(f"error: no writable field '{field}' in {args.struct_name}")

    skipped = {n: i for n, i in layout.items() if n not in fields}
    print_layout(args.struct_name, fields, skipped)

    port = None if args.dry_run else (args.port or autodetect_port())
    where = "dry run, nothing will be sent" if args.dry_run else f"sending to {port}"
    print(f"\n{where}. Enter a value, or '<field> <value>' to switch fields. Ctrl-D quits.\n")

    link = None if args.dry_run else serial.Serial(port, 115200, timeout=1)
    try:
        while True:
            try:
                line = input(f"{field} = ").split()
            except (EOFError, KeyboardInterrupt):
                print()
                return

            if not line:
                continue
            if len(line) == 2:
                name, text = line
                if name not in fields:
                    print(f"  no writable field '{name}'")
                    continue
                field = name
            elif len(line) == 1:
                text = line[0]
            else:
                print("  expected '<value>' or '<field> <value>'")
                continue

            info = fields[field]
            try:
                value = parse_value(text, info["type"])
            except ValueError as err:
                print(f"  {err}")
                continue

            packet = frame(info["offset"], value)
            print(f"  offset {info['offset']}, value {value} -> {packet.hex(' ')}")
            if link is not None:
                link.write(packet)
                link.flush()
    finally:
        if link is not None:
            link.close()


if __name__ == "__main__":
    main()
