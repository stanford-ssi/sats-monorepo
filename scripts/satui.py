#!/usr/bin/env python3
"""
satui.py - browse and poke the slate of a running board.

Field offsets come from the firmware ELF's debug info rather than from a
hardcoded table, so an offset always matches the binary that is actually
flashed. Commands go out as cobs framed SatCmds on the pico's cdc port and
every one of them is answered, so the table shows what the board really
holds rather than what we asked it to hold.

Usage:
    uv run scripts/satui.py                       # tui, autodetected port
    uv run scripts/satui.py --port /dev/ttyACM0
    uv run scripts/satui.py --fake                # tui against a fake board
    uv run scripts/satui.py --list                # print the layout, exit
    uv run scripts/satui.py --dry-run             # print frames, send nothing
    uv run scripts/satui.py --set sleep_ms=500 --set temperature=36.5
"""

import argparse
import os
import subprocess
import sys

import cobs
import theme
import tui
from fake_board import FakeBoard
from link import Link, LoopbackTransport, NullTransport, SerialTransport, autodetect_port
from parse_slate import get_struct_layout
from protocol import fields_from_layout, format_value, parse_value, read_cmd, write_cmd

DEFAULT_ELF = "bazel-bin/blink"
DEFAULT_STRUCT = "Slate"


def resolve_elf(elf: str) -> str:
    """Locate the firmware elf, working around the bazel-bin symlink.

    Bazel repoints `bazel-bin` at whichever configuration it built last, so
    running the host tests leaves the default path aimed at a tree with no
    firmware in it. Rather than fail with a bare "no such file", ask bazel
    where the pico build actually puts things.
    """
    if os.path.exists(elf) or elf != DEFAULT_ELF:
        return elf

    try:
        out = subprocess.run(
            ["bazel", "cquery", "--config=pico", "--output=files", "//:blink"],
            capture_output=True, text=True, timeout=300, check=True)
    except (OSError, subprocess.SubprocessError):
        return elf  # no bazel, or no pico build yet; report the missing default

    for path in out.stdout.split():
        if path.endswith("/blink") and os.path.exists(path):
            return path
    return elf


def discover(elf: str, struct_name: str):
    """The addressable fields of `struct_name`, flattened out of the elf."""
    try:
        layout = get_struct_layout(elf, struct_name)
    except (FileNotFoundError, ValueError) as err:
        raise SystemExit(f"error: {err}")

    fields, skipped = fields_from_layout(layout)
    if not fields:
        raise SystemExit(f"error: {struct_name} has no addressable fields")
    for name, why in skipped.items():
        print(f"note: skipping {name}, {why}", file=sys.stderr)
    return fields


def open_link(args, fields) -> tuple[Link, str]:
    """The link, and a label for it to show in the ui."""
    if args.dry_run:
        return Link(NullTransport(), timeout=0), "dry run"  # nothing answers
    if args.fake:
        size = max(f.offset + f.size for f in fields)
        return Link(LoopbackTransport(FakeBoard(size))), "fake board"
    port = args.port or autodetect_port()
    return Link(SerialTransport(port)), port


def run_headless(link: Link, fields: list, sets: list) -> None:
    """Print the frame for each operation, and whatever comes back.

    With no --set this just reads every field, which is enough to exercise
    the encoder and the framing without a board on the other end.
    """
    by_name = {f.name: f for f in fields}
    ops = []
    for assignment in sets:
        name, _, text = assignment.partition("=")
        if name not in by_name:
            raise SystemExit(f"error: no field '{name}'")
        field = by_name[name]
        try:
            ops.append((field, write_cmd(field, parse_value(text, field))))
        except ValueError as err:
            raise SystemExit(f"error: {name}: {err}")
    if not sets:
        ops = [(f, read_cmd(f)) for f in fields]

    for field, cmd in ops:
        print(f"{field.name:<24} {cobs.frame(cmd.SerializeToString()).hex(' ')}")
        response = link.request(cmd)
        if response is not None:
            print(f"{'':<24} -> {format_value(response)}")


def print_layout(struct_name: str, fields: list) -> None:
    print(f"struct {struct_name}:")
    for f in fields:
        print(f"  {f.name:<24} offset {f.offset:>3}  {f.type_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--elf", default=DEFAULT_ELF, help=f"firmware elf (default {DEFAULT_ELF})")
    parser.add_argument("--struct", default=DEFAULT_STRUCT, dest="struct_name")
    parser.add_argument("--port", help="serial port (autodetected if omitted)")
    parser.add_argument("--fake", action="store_true", help="talk to an in process fake board")
    parser.add_argument("--dry-run", action="store_true", help="print the frames instead of sending them")
    parser.add_argument("--list", action="store_true", help="print the discovered fields and exit")
    parser.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE",
                        help="write a field and exit, repeatable")
    args = parser.parse_args()

    fields = discover(resolve_elf(args.elf), args.struct_name)
    if args.list:
        print_layout(args.struct_name, fields)
        return

    link, where = open_link(args, fields)
    try:
        if args.dry_run or args.set:
            run_headless(link, fields, args.set)
        else:
            app = tui.App(fields, link, theme=theme.Theme.detect(),
                          title=args.struct_name, subtitle=where)
            tui.main(app)
    finally:
        link.close()


if __name__ == "__main__":
    main()
