"""
satcmd - talk to a board's slate by name over the SatCmd protocol.

    import satcmd

    with satcmd.connect() as sat:
        sat.sleep_ms = 500
        assert sat.sleep_ms == 500

See sat.py for the object you get back, link.py for raw offset/width access
and the symmetric request/serve machinery underneath it.
"""

from satcmd.layout import Field, Layout
from satcmd.link import BadAddress, BadWidth, Link, SatError, Timeout
from satcmd.memory import FakeBoard, MemoryServer
from satcmd.sat import Group, Sat, connect

__all__ = [
    "BadAddress",
    "BadWidth",
    "FakeBoard",
    "Field",
    "Group",
    "Layout",
    "Link",
    "MemoryServer",
    "Sat",
    "SatError",
    "Timeout",
    "connect",
]
