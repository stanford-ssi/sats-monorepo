#!/usr/bin/env python3
"""
link.py - carrying SatCmds to a board and SatResponses back.

A Link is the framing and the request/reply pairing; a transport is just
somewhere to put bytes. Splitting them is what lets the fake board sit
behind the same Link the real serial port does.
"""

import time

from google.protobuf.message import DecodeError

import cobs
from sats_proto import SatCmd, SatResponse

RASPBERRY_PI_VID = 0x2E8A
BAUD = 115200

# The board answers in under a millisecond, so this is only ever hit when
# something is wrong; it is short enough to keep the ui responsive.
DEFAULT_TIMEOUT = 0.3


class SerialTransport:
    """The real thing: a pico's usb cdc port."""

    def __init__(self, port: str, baud: int = BAUD):
        import serial  # only needed on the hardware path

        self.port = port
        self._link = serial.Serial(port, baud, timeout=0)

    def write(self, data: bytes) -> None:
        self._link.write(data)
        self._link.flush()

    def read(self) -> bytes:
        return self._link.read(self._link.in_waiting or 1)

    def close(self) -> None:
        self._link.close()


class LoopbackTransport:
    """Wires a Link straight into a FakeBoard, no port involved."""

    def __init__(self, board):
        self.board = board
        self._pending = bytearray()

    def write(self, data: bytes) -> None:
        self._pending += self.board.feed(data)

    def read(self) -> bytes:
        out, self._pending = bytes(self._pending), bytearray()
        return out

    def close(self) -> None:
        pass


class NullTransport:
    """Dry run: remembers what would have gone out, answers nothing."""

    def __init__(self):
        self.sent: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.sent.append(data)

    def read(self) -> bytes:
        return b""

    def close(self) -> None:
        pass


class Link:
    """Sends commands and matches up the replies."""

    def __init__(self, transport, timeout: float = DEFAULT_TIMEOUT):
        self.transport = transport
        self.timeout = timeout
        self._deframer = cobs.Deframer()

    def send(self, cmd: SatCmd) -> bytes:
        """Frame and write one command, returning the bytes that went out."""
        packet = cobs.frame(cmd.SerializeToString())
        self.transport.write(packet)
        return packet

    def request(self, cmd: SatCmd) -> SatResponse | None:
        """Send a command and wait for its reply, or None if none arrives.

        The board answers every command with exactly one response, so any
        reply still in flight from an earlier timed out command would be
        mistaken for this one; the queue is drained first to avoid that.
        """
        self._drain()
        self.send(cmd)

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            frames = self._deframer.push(self.transport.read())
            if frames:
                return _parse(frames[0])
            time.sleep(0.001)
        return None

    def close(self) -> None:
        self.transport.close()

    def _drain(self) -> None:
        self._deframer.push(self.transport.read())


def _parse(payload: bytes) -> SatResponse | None:
    response = SatResponse()
    try:
        response.ParseFromString(payload)
    except DecodeError:
        return None
    return response


def autodetect_port() -> str:
    """The one attached raspberry pi usb device, if there is exactly one."""
    from serial.tools import list_ports

    ports = [p for p in list_ports.comports() if p.vid == RASPBERRY_PI_VID]
    if not ports:
        raise SystemExit(
            "error: no raspberry pi usb device found, pass --port explicitly"
        )
    if len(ports) > 1:
        found = ", ".join(p.device for p in ports)
        raise SystemExit(f"error: several candidates ({found}), pass --port")
    return ports[0].device
