"""
memory.py - the answering side of the protocol, in python.

MemoryServer is a line for line twin of common/slate/slate_server.hpp: the
same width, bounds and alignment rules, the same echo on failure. Put it
behind a Link and python can serve a slate exactly the way a board does,
which is all FakeBoard is.
"""

from satcmd.link import Link, pipe
from satcmd.proto import RESPONSE_TO, WIDTHS, SatMsg, SatMsgType, Status


class MemoryServer:
    """Answers READ and WRITE requests against a bytearray."""

    def __init__(self, memory: bytearray):
        self.memory = memory

    def handle(self, msg: SatMsg) -> SatMsg | None:
        if msg.type not in RESPONSE_TO:
            return None  # a response, or nonsense; nothing to answer

        rsp = SatMsg(type=RESPONSE_TO[msg.type], offset=msg.offset, width=msg.width)
        if msg.width not in WIDTHS:
            rsp.status = Status.STATUS_BAD_WIDTH
            return rsp
        if not self._addressable(msg.offset, msg.width):
            rsp.status = Status.STATUS_BAD_ADDRESS
            return rsp

        span = slice(msg.offset, msg.offset + msg.width)
        if msg.type == SatMsgType.SAT_MSG_TYPE_WRITE:
            # Bytes past `width` are dropped, as the memcpy on the board does.
            low = msg.value & ((1 << (8 * msg.width)) - 1)
            self.memory[span] = low.to_bytes(msg.width, "little")

        rsp.status = Status.STATUS_OK
        rsp.value = int.from_bytes(self.memory[span], "little")
        return rsp

    def _addressable(self, offset: int, width: int) -> bool:
        return offset % width == 0 and offset + width <= len(self.memory)


class FakeBoard:
    """A slate in process, served by a Link of its own.

    Hand `transport` to a requesting Link. The board's end of the pipe
    answers each request as it arrives, so a request is already answered
    by the time the write that sent it returns: no threads, no timing.
    """

    def __init__(self, size: int):
        self.memory = bytearray(size)
        self.transport, board_end = pipe()
        self.link = Link(board_end, server=MemoryServer(self.memory), name="fake")
        board_end.on_receive = self.link.poll
