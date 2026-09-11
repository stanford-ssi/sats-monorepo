"""The stand in board, and the whole stack running through it."""

import pytest

import cobs
from fake_board import FakeBoard
from link import Link, LoopbackTransport, NullTransport
from protocol import Field, read_cmd, response_value, write_cmd
from sats_proto import SatCmd, SatResponse, Status, Width

SLEEP_MS = Field("sleep_ms", 0, Width.WIDTH_U32)
TEMPERATURE = Field("temperature", 4, Width.WIDTH_F32)
MODE = Field("mode", 16, Width.WIDTH_U8)


@pytest.fixture
def link():
    """A Link wired straight into a fake board, no port in the middle."""
    board = FakeBoard(size=20)
    link = Link(LoopbackTransport(board), timeout=0.05)
    link.board = board  # handy for asserting on what actually landed
    return link


@pytest.mark.parametrize(
    "field, value",
    [
        (SLEEP_MS, 500),
        (TEMPERATURE, 36.5),
        (MODE, 0xAB),
    ],
)
def test_write_then_read_back(link, field, value):
    """Encode, frame, transport, deframe, decode, and do it again backwards."""
    written = link.request(write_cmd(field, value))
    assert written.status == Status.STATUS_OK
    assert written.offset == field.offset
    assert response_value(written) == pytest.approx(value)

    read = link.request(read_cmd(field))
    assert read.status == Status.STATUS_OK
    assert response_value(read) == pytest.approx(value)


def test_write_is_answered_with_what_landed(link):
    """A u8 write of 0x1FF keeps the low byte, and says so."""
    response = link.request(write_cmd(Field("mode", 16, Width.WIDTH_U8), 0xFF))
    assert response_value(response) == 0xFF
    assert link.board.memory[16] == 0xFF


def test_writes_do_not_disturb_neighbours(link):
    link.request(write_cmd(SLEEP_MS, 0xFFFFFFFF))
    link.request(write_cmd(MODE, 1))
    assert link.request(read_cmd(SLEEP_MS)).uint_value == 0xFFFFFFFF
    assert link.board.memory[17:20] == bytearray(3)


@pytest.mark.parametrize(
    "offset, width",
    [
        (20, Width.WIDTH_U8),  # one past the end
        (17, Width.WIDTH_U32),  # straddles the end
        (2, Width.WIDTH_U32),  # misaligned
        (1, Width.WIDTH_U16),  # misaligned
    ],
)
def test_bad_offsets_are_rejected(link, offset, width):
    read = SatCmd()
    read.read.offset = offset
    read.read.width = width
    assert link.request(read).status == Status.STATUS_BAD_OFFSET


def test_rejected_write_leaves_memory_alone(link):
    write = SatCmd()
    write.write_u32.offset = 2  # misaligned
    write.write_u32.value = 0xFFFFFFFF
    assert link.request(write).status == Status.STATUS_BAD_OFFSET
    assert link.board.memory == bytearray(20)


def test_read_without_a_width_is_a_bad_command(link):
    """There is no field to read, so it is the command that is wrong."""
    read = SatCmd()
    read.read.offset = 0
    read.read.width = Width.WIDTH_UNSPECIFIED
    response = link.request(read)
    assert response.status == Status.STATUS_BAD_COMMAND
    assert response.offset == 0  # echoed back even on a refusal


def test_empty_command_is_a_bad_command():
    """A SatCmd with no variant set is undecodable as an instruction."""
    board = FakeBoard()
    response = SatResponse.FromString(board.handle(b"\x38\x01"))  # unknown field 7
    assert response.status == Status.STATUS_BAD_COMMAND


def test_garbage_gets_no_reply():
    """CmdReceiver drops an undecodable frame, so nothing ever answers it."""
    board = FakeBoard()
    assert board.handle(b"\xff\xff\xff") is None
    assert board.feed(cobs.frame(b"\xff\xff\xff")) == b""


def test_stray_delimiters_produce_no_replies():
    """The board must not answer the idle link."""
    assert FakeBoard().feed(b"\x00\x00\x00") == b""


def test_two_commands_in_one_write(link):
    """Framing has to survive commands arriving back to back."""
    stream = cobs.frame(write_cmd(SLEEP_MS, 7).SerializeToString())
    stream += cobs.frame(read_cmd(SLEEP_MS).SerializeToString())
    replies = link.transport.board.feed(stream)
    assert len(cobs.Deframer().push(replies)) == 2


def test_silence_is_reported_rather_than_swallowed():
    """Nothing on the far end has to look different from a zero reading."""
    link = Link(NullTransport(), timeout=0)
    assert link.request(read_cmd(SLEEP_MS)) is None
