"""
link.py - one end of a SatCmd link.

The protocol is symmetric, and so is this: a Link sends requests and waits
for their responses, and if it was given a server it answers the requests
that arrive from the far end too. A transport is just somewhere to put
bytes, which is what lets the fake board and a real serial port sit behind
the same Link.

Values cross a Link as raw unsigned integers. What those bits mean is the
caller's business; see layout.Field.
"""

import logging
import time
from typing import Protocol

from google.protobuf.message import DecodeError

from satcmd import cobs
from satcmd.proto import RESPONSE_TO, SatMsg, SatMsgType, Status

log = logging.getLogger(__name__)

RASPBERRY_PI_VID = 0x2E8A
BAUD = 115200

# The board answers in under a millisecond, so this is only ever hit when
# something is wrong; it is short enough to keep the ui responsive.
DEFAULT_TIMEOUT = 0.3


class SatError(Exception):
    """A request that did not get a usable answer."""


class Timeout(SatError):
    """Nothing answered in time."""


class BadAddress(SatError):
    """The far end refused the offset: out of bounds, or misaligned."""


class BadWidth(SatError):
    """The far end refused the width."""


STATUS_ERRORS = {
    Status.STATUS_BAD_ADDRESS: BadAddress,
    Status.STATUS_BAD_WIDTH: BadWidth,
}


class Transport(Protocol):
    def write(self, data: bytes) -> None: ...
    def read(self) -> bytes: ...  # whatever has arrived, possibly nothing
    def close(self) -> None: ...


class Server(Protocol):
    def handle(self, msg: SatMsg) -> SatMsg | None: ...


class SerialTransport:
    """The real thing: a pico's usb cdc port."""

    def __init__(self, port: str, baud: int = BAUD):
        import serial  # only needed on the hardware path

        self.port = port
        self._serial = serial.Serial(port, baud, timeout=0)

    def write(self, data: bytes) -> None:
        self._serial.write(data)
        self._serial.flush()

    def read(self) -> bytes:
        return self._serial.read(self._serial.in_waiting or 1)

    def close(self) -> None:
        self._serial.close()

    def __repr__(self) -> str:
        return self.port


class PipeEnd:
    """One end of an in process byte pipe, see pipe()."""

    def __init__(self):
        self.peer: PipeEnd | None = None
        self.on_receive = None  # called after the peer writes to us
        self._inbox = bytearray()

    def write(self, data: bytes) -> None:
        self.peer._inbox += data
        if self.peer.on_receive is not None:
            self.peer.on_receive()

    def read(self) -> bytes:
        out, self._inbox = bytes(self._inbox), bytearray()
        return out

    def close(self) -> None:
        pass

    def __repr__(self) -> str:
        return "<pipe>"


def pipe() -> tuple[PipeEnd, PipeEnd]:
    """Two transports wired back to back: one's writes are the other's reads."""
    a, b = PipeEnd(), PipeEnd()
    a.peer, b.peer = b, a
    return a, b


class Link:
    """Sends SatMsgs, matches up the responses, and optionally serves."""

    def __init__(
        self,
        transport: Transport,
        server: Server | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        name: str = "link",  # tells the ends apart in the debug log
    ):
        self.transport = transport
        self.server = server
        self.timeout = timeout
        self.name = name
        self._deframer = cobs.Deframer()

    def send(self, msg: SatMsg) -> None:
        """Frame and write one message of any type."""
        log.debug("%s tx %s", self.name, _describe(msg))
        self.transport.write(cobs.frame(msg.SerializeToString()))

    def poll(self) -> list[SatMsg]:
        """Take in whatever has arrived. Requests are answered by the server
        (or dropped without one); everything else is returned."""
        others = []
        for payload in self._deframer.push(self.transport.read()):
            msg = _parse(payload)
            if msg is None:
                continue
            log.debug("%s rx %s", self.name, _describe(msg))
            if msg.type in RESPONSE_TO:  # a request, for us to answer
                if self.server is not None:
                    reply = self.server.handle(msg)
                    if reply is not None:
                        self.send(reply)
            else:
                others.append(msg)
        return others

    def request(self, msg: SatMsg) -> SatMsg:
        """Send a request and return its response, whatever its status.

        A response is recognised by its type, offset and width, which the
        far end echoes. Anything else that turns up meanwhile, such as the
        late answer to an earlier request that timed out, is discarded.
        """
        want = RESPONSE_TO[msg.type]
        self.poll()  # flush anything stale before it can be mistaken for ours
        self.send(msg)

        deadline = time.monotonic() + self.timeout
        while True:
            for rsp in self.poll():
                if (rsp.type, rsp.offset, rsp.width) == (want, msg.offset, msg.width):
                    return rsp
            if time.monotonic() >= deadline:
                raise Timeout(
                    f"no response to {_describe(msg)} within {self.timeout:g}s"
                )
            time.sleep(0.0005)

    def read(self, offset: int, width: int) -> int:
        """The raw bytes at `offset`, as an unsigned little endian integer."""
        return self._value(
            self.request(
                SatMsg(type=SatMsgType.SAT_MSG_TYPE_READ, offset=offset, width=width)
            )
        )

    def write(self, offset: int, width: int, value: int) -> int:
        """Store raw bytes at `offset` and return what landed there."""
        msg = SatMsg(
            type=SatMsgType.SAT_MSG_TYPE_WRITE, offset=offset, width=width, value=value
        )
        return self._value(self.request(msg))

    def close(self) -> None:
        self.transport.close()

    @staticmethod
    def _value(rsp: SatMsg) -> int:
        if rsp.status != Status.STATUS_OK:
            error = STATUS_ERRORS.get(rsp.status, SatError)
            raise error(
                f"{Status.Name(rsp.status)} for offset {rsp.offset} width {rsp.width}"
            )
        return rsp.value


def _parse(payload: bytes) -> SatMsg | None:
    msg = SatMsg()
    try:
        msg.ParseFromString(payload)
    except DecodeError:
        return None
    return msg


def _describe(msg: SatMsg) -> str:
    """A one line summary for logs and error messages."""
    text = f"{SatMsgType.Name(msg.type)} @{msg.offset} w{msg.width}"
    if msg.type != SatMsgType.SAT_MSG_TYPE_READ:
        text += f" = {msg.value:#x}"
    if msg.status != Status.STATUS_OK:
        text += f" {Status.Name(msg.status)}"
    return text


def autodetect_port() -> str:
    """The one attached raspberry pi usb device, if there is exactly one."""
    from serial.tools import list_ports

    ports = [p for p in list_ports.comports() if p.vid == RASPBERRY_PI_VID]
    if not ports:
        raise SatError("no raspberry pi usb device found, pass a port explicitly")
    if len(ports) > 1:
        found = ", ".join(p.device for p in ports)
        raise SatError(f"several candidate ports ({found}), pass one explicitly")
    return ports[0].device
