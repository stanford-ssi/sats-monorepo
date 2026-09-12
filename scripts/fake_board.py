#!/usr/bin/env python3
"""
fake_board.py - a slate that answers commands, in process.

Stands in for the flight software so the whole stack (encode, frame,
transport, deframe, decode, readback) can be exercised with no pico
attached. It speaks the same bytes over the same framing and applies the
same bounds and alignment rules, so anything that fools it should fool the
board too.
"""

import struct

from google.protobuf.message import DecodeError

import cobs
from protocol import SIGNED, WIDTH_BYTES
from sats_proto import SatCmd, SatResponse, Status, Width


def _wrap_signed(value: int, size: int) -> int:
    """Narrow to `size` bytes the way a c++20 static_cast does."""
    bits = 8 * size
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >= 1 << (bits - 1) else value


# How each width is packed into slate memory, little endian like the rp2350.
PACK = {
    Width.WIDTH_U8: "<B",
    Width.WIDTH_U16: "<H",
    Width.WIDTH_U32: "<I",
    Width.WIDTH_F32: "<f",
    Width.WIDTH_BOOL: "<B",  # stored as a byte, same as SlateWriter does
    Width.WIDTH_I8: "<b",
    Width.WIDTH_I16: "<h",
    Width.WIDTH_I32: "<i",
}

# Which write variant carries which width.
WRITE_WIDTHS = {
    "write_u8": Width.WIDTH_U8,
    "write_u16": Width.WIDTH_U16,
    "write_u32": Width.WIDTH_U32,
    "write_f32": Width.WIDTH_F32,
    "write_bool": Width.WIDTH_BOOL,
    "write_i8": Width.WIDTH_I8,
    "write_i16": Width.WIDTH_I16,
    "write_i32": Width.WIDTH_I32,
}


class FakeBoard:
    """A byte addressable slate plus the command handling around it."""

    def __init__(self, size: int = 16):
        self.memory = bytearray(size)
        self.commands: list[SatCmd] = []  # everything accepted, for assertions
        self._deframer = cobs.Deframer()

    def feed(self, data: bytes) -> bytes:
        """Consume received bytes and return the frames to send back."""
        out = bytearray()
        for payload in self._deframer.push(data):
            response = self.handle(payload)
            if response is not None:
                out += cobs.frame(response)
        return bytes(out)

    def handle(self, payload: bytes) -> bytes | None:
        """One command frame in, one serialised SatResponse out.

        Returns None for a frame nanopb would refuse: CmdReceiver drops
        those before anything can reply to them, so the ground has to cope
        with silence, not with an error.
        """
        cmd = SatCmd()
        try:
            cmd.ParseFromString(payload)
        except DecodeError:
            return None

        variant = cmd.WhichOneof("cmd")
        if variant is None:
            # Decodable, but not an instruction. SlateWriter answers this one.
            return self._error(Status.STATUS_BAD_COMMAND)

        self.commands.append(cmd)
        body = getattr(cmd, variant)
        if variant == "read":
            return self._read(body.offset, body.width)

        width = WRITE_WIDTHS[variant]
        value = body.value
        if width == Width.WIDTH_BOOL:
            value = 1 if value else 0  # normalised, as SlateWriter does
        elif width in SIGNED:
            value = _wrap_signed(value, WIDTH_BYTES[width])
        elif width != Width.WIDTH_F32:
            value &= (1 << (8 * WIDTH_BYTES[width])) - 1  # truncated to the width
        return self._write(body.offset, width, value)

    def peek(self, offset: int, width: int):
        """Read slate memory directly, bypassing the command path."""
        return struct.unpack_from(PACK[width], self.memory, offset)[0]

    def poke(self, offset: int, width: int, value) -> None:
        """Write slate memory directly, e.g. to set up a test's initial state."""
        struct.pack_into(PACK[width], self.memory, offset, value)

    def _addressable(self, offset: int, width: int) -> bool:
        """SlateWriter only touches an in bounds, naturally aligned slot."""
        size = WIDTH_BYTES[width]
        return offset % size == 0 and offset + size <= len(self.memory)

    def _read(self, offset: int, width: int) -> bytes:
        if width not in WIDTH_BYTES:
            # Nothing to read: the request is not interpretable at all.
            return self._error(Status.STATUS_BAD_COMMAND, offset, width)
        if not self._addressable(offset, width):
            return self._error(Status.STATUS_BAD_OFFSET, offset, width)
        return self._ok(offset, width, self.peek(offset, width))

    def _write(self, offset: int, width: int, value) -> bytes:
        if not self._addressable(offset, width):
            return self._error(Status.STATUS_BAD_OFFSET, offset, width)
        self.poke(offset, width, value)
        # Answer with what actually landed rather than what was asked for.
        return self._ok(offset, width, self.peek(offset, width))

    def _ok(self, offset: int, width: int, value) -> bytes:
        response = SatResponse(status=Status.STATUS_OK, offset=offset, width=width)
        if width == Width.WIDTH_F32:
            response.float_value = value
        elif width in SIGNED:
            response.int_value = value
        elif width == Width.WIDTH_BOOL:
            # A byte other than 0 or 1 still reads back as true, which is
            # what load<uint8_t>(offset) != 0 does on the board.
            response.bool_value = bool(value)
        else:
            response.uint_value = value
        return response.SerializeToString()

    def _error(
        self, status: int, offset: int = 0, width: int = Width.WIDTH_UNSPECIFIED
    ) -> bytes:
        return SatResponse(
            status=status, offset=offset, width=width
        ).SerializeToString()
