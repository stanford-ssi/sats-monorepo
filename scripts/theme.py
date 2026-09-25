#!/usr/bin/env python3
"""
theme.py - colours and box glyphs, with a plain variant.

Everything visual lives here so the ui code stays about layout. A Theme
with colour off returns its text untouched, which is what the tests and a
redirected stdout get.
"""

import os
import re
import sys

# SGR parameters, named so the call sites read as intent not as numbers.
BOLD = "1"
DIM = "2"
REVERSE = "7"
RED = "31"
GREEN = "32"
YELLOW = "33"
BLUE = "34"
CYAN = "36"

RESET = "\x1b[0m"

ANSI = re.compile(r"\x1b\[[0-9;]*m")

ROUND = {"h": "─", "v": "│", "tl": "╭", "tr": "╮", "bl": "╰", "br": "╯"}
ASCII = {"h": "-", "v": "|", "tl": "+", "tr": "+", "bl": "+", "br": "+"}


def visible_len(text: str) -> int:
    """Length as the terminal will draw it, ignoring colour codes."""
    return len(ANSI.sub("", text))


class Theme:
    """Wraps text in SGR codes, or doesn't."""

    def __init__(self, color: bool = True, unicode: bool = True):
        self.color = color
        self.box = ROUND if unicode else ASCII
        self.marker = "›" if unicode else ">"
        self.sep = "·" if unicode else "-"
        self.caret = "▏" if unicode else "_"
        self.ellipsis = "…" if unicode else "..."

    def __call__(self, text: str, *codes: str) -> str:
        if not self.color or not codes:
            return text
        return f"\x1b[{';'.join(codes)}m{text}{RESET}"

    @classmethod
    def detect(cls, stream=None) -> "Theme":
        """What the terminal on the other end can actually handle.

        NO_COLOR is honoured because it is the convention, and a redirected
        stdout gets neither colour nor box drawing so the output stays
        greppable.
        """
        stream = stream or sys.stdout
        tty = hasattr(stream, "isatty") and stream.isatty()
        color = (
            tty and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
        )
        encoding = (getattr(stream, "encoding", "") or "").lower()
        return cls(color=color, unicode=tty and "utf" in encoding)


PLAIN = Theme(color=False, unicode=False)
