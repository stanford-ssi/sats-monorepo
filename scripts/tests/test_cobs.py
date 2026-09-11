"""Framing: it has to agree with common/cobs/cobs.cpp byte for byte."""

import pytest

import cobs

# The frame the firmware produced for "write 250 to offset 0" back when a
# SatCmd was two top level fields. The schema has moved on, the framing has
# not, so this is still a valid encoder/decoder vector.
REFERENCE_PAYLOAD = bytes.fromhex("08 00 10 fa 01")
REFERENCE_FRAME = bytes.fromhex("02 08 04 10 fa 01 00")


def test_reference_vector():
    assert cobs.frame(REFERENCE_PAYLOAD) == REFERENCE_FRAME
    assert cobs.decode(REFERENCE_FRAME) == REFERENCE_PAYLOAD


@pytest.mark.parametrize("payload", [
    b"\x01",
    b"\x01\x02\x03",
    b"\x00\x01\x00\x02\x00",  # embedded zeros, including at both ends
    bytes(range(1, 255)),  # exactly one full block
    bytes([0xAB]) * 300,  # spills past the 254 byte block limit
    bytes(range(256)) * 2,  # long, with zeros
])
def test_round_trip(payload):
    assert cobs.decode(cobs.frame(payload)) == payload
    assert b"\x00" not in cobs.encode(payload)


def test_empty_payload_is_refused():
    """Proto3 can serialise a message to nothing; that must not reach the wire."""
    with pytest.raises(ValueError):
        cobs.frame(b"")


def test_deframer_reassembles_across_chunks():
    """Usb hands over whatever arrived, not whole frames."""
    stream = cobs.frame(b"\x01\x00\x02") + cobs.frame(b"hello")
    deframer = cobs.Deframer()
    out = []
    for i in range(len(stream)):  # one byte at a time, the worst case
        out += deframer.push(stream[i:i + 1])
    assert out == [b"\x01\x00\x02", b"hello"]


def test_stray_delimiters_are_dropped():
    """An idle link is all zeros; none of them are frames."""
    deframer = cobs.Deframer()
    assert deframer.push(b"\x00\x00\x00") == []
    assert deframer.push(cobs.frame(b"\x07")) == [b"\x07"]


def test_overlong_frames_are_dropped_whole():
    """Better no command than a truncated prefix of one."""
    deframer = cobs.Deframer(max_frame=4)
    assert deframer.push(cobs.frame(b"12345678")) == []
    assert deframer.push(cobs.frame(b"12")) == [b"12"]
