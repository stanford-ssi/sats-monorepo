#!/usr/bin/env python3
"""
cobs.py - the wire framing shared with the firmware.

Frames are cobs encoded and delimited by a zero byte, so a zero can never
appear inside a frame and a receiver can always resynchronise on one. This
is a direct port of common/cobs/cobs.cpp and the streaming decoder in
common/cmd_receiver/cmd_receiver.cpp; keep the three in step.
"""

DELIMITER = b"\x00"

# Longest run of non zero bytes cobs can carry under a single code byte.
BLOCK_MAX = 254


def encode(data: bytes) -> bytes:
    """Cobs encode `data`, not including the trailing zero delimiter.

    The payload is split into blocks of up to 254 non zero bytes, each
    prefixed by a code byte holding the block length with the code byte
    included. A code of 0xff means the block was cut short by the length
    limit rather than by a zero, so no zero is restored there.
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
            block_full = len(block) == BLOCK_MAX
            if block_full:
                out.append(0xFF)
                out += block
                block.clear()

    if not block_full:
        out.append(len(block) + 1)
        out += block
    return bytes(out)


def frame(payload: bytes) -> bytes:
    """The complete byte sequence to push down the wire for one message.

    Refuses an empty payload: it would encode to a lone code byte plus the
    delimiter, which every receiver here treats as a stray delimiter and
    drops. Proto3 omits zero valued fields, so this is a real hazard for any
    message whose fields all happen to be zero.
    """
    if not payload:
        raise ValueError("empty payload would be dropped as a stray delimiter")
    return encode(payload) + DELIMITER


class Deframer:
    """Streaming cobs decoder, a port of CmdReceiver's.

    Bytes are fed in as they arrive; complete payloads come back out of
    push(). Frames longer than `max_frame` are dropped whole at the
    delimiter rather than handed over truncated.
    """

    def __init__(self, max_frame: int = 256):
        self.max_frame = max_frame
        self._code = 0  # length of the block being decoded, code byte included
        self._pos = 0  # bytes of that block consumed so far
        self._buf = bytearray()
        self._overflowed = False

    def push(self, data: bytes) -> list[bytes]:
        """Feed received bytes, returning whatever frames they completed."""
        frames = []
        for byte in data:
            if byte == 0:
                payload = self._finish()
                if payload is not None:
                    frames.append(payload)
                continue

            decoded = self._decode(byte)
            if decoded is None:
                continue
            if len(self._buf) < self.max_frame:
                self._buf.append(decoded)
            else:
                self._overflowed = True
        return frames

    def _decode(self, next_byte: int) -> int | None:
        """Decode one non delimiter byte, or None if it was just a code byte."""
        if self._pos < self._code:
            self._pos += 1
            return next_byte  # plain payload byte inside the current block

        # The previous block is done, so `next_byte` starts a new one.
        zero_stripped = self._code not in (0, 0xFF)
        self._code = next_byte
        self._pos = 1
        return 0 if zero_stripped else None

    def _finish(self) -> bytes | None:
        payload = bytes(self._buf)
        usable = not self._overflowed
        self._code = 0
        self._pos = 0
        self._buf.clear()
        self._overflowed = False

        # An empty frame is just a stray delimiter, e.g. an idle link.
        return payload if usable and payload else None


def decode(encoded: bytes) -> bytes:
    """Decode a single cobs frame, with or without its trailing delimiter."""
    frames = Deframer(max_frame=len(encoded) + 1).push(encoded + DELIMITER)
    if not frames:
        raise ValueError("not a decodable cobs frame")
    return frames[0]
