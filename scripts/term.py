#!/usr/bin/env python3
"""
term.py - a bottom anchored terminal driver.

Draws into the last few lines of the terminal instead of taking it over.
Nothing already on screen is painted on, there is no alternate screen to
switch back out of, and the last frame is simply left behind when the
program exits, so the ui reads like ordinary stdout once it is done.

That is the whole reason this is not curses: curses owns the full screen
by design, and leaves nothing behind when it gives it back.
"""

import os
import re
import select
import shutil
import sys
import termios
import tty

from theme import ANSI, visible_len

HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
CLEAR_LINE = "\x1b[2K"

# How long to wait for the rest of an escape sequence before deciding the
# user just pressed Esc. Long enough for a keystroke to arrive whole, short
# enough that Esc does not feel like it hung.
ESC_TIMEOUT = 0.03

ESCAPES = {
    "[A": "UP",
    "[B": "DOWN",
    "[C": "RIGHT",
    "[D": "LEFT",
    "[H": "HOME",
    "[F": "END",
    "[5~": "PGUP",
    "[6~": "PGDN",
    "OH": "HOME",
    "OF": "END",
}

CONTROL = {
    "\r": "ENTER",
    "\n": "ENTER",
    "\x7f": "BACKSPACE",
    "\x08": "BACKSPACE",
    "\x03": "q",  # ctrl-c reads as quit rather than a traceback
}


# One keystroke: a csi/ss3 escape sequence, or a single character with any
# utf-8 continuation bytes that belong to it.
KEYSTROKE = re.compile(
    rb"\x1b(?:\[[0-9;]*[A-Za-z~]|O[A-Za-z])|[\x00-\x7f]|[\xc0-\xff][\x80-\xbf]*"
)


def next_key(pending: bytes) -> tuple[str, bytes]:
    """Split the first keystroke off a buffer, returning it and the rest.

    Keys have to be taken from a byte buffer rather than read one at a
    time, because a paste or a fast typist delivers several at once and
    anything left behind would not show up in the next select().
    """
    match = KEYSTROKE.match(pending)
    if not match:
        return "", pending[1:]  # an unusable leading byte, drop it
    return match.group().decode("utf8", "replace"), pending[match.end() :]


def decode(seq: str) -> str | None:
    """Turn one keystroke's bytes into the name App expects."""
    if not seq:
        return None
    if seq == "\x1b":
        return "ESC"
    if seq.startswith("\x1b"):
        return ESCAPES.get(seq[1:])  # unknown sequences are ignored
    return CONTROL.get(seq, seq)


def cursor_up(lines: int) -> str:
    return f"\x1b[{lines}A" if lines > 0 else ""


def resize(old: int, new: int) -> str:
    """What to write to make the block `new` lines tall instead of `old`.

    The cursor starts and finishes on the block's last line, which is
    where draw() counts up from.

    Two things this deliberately does not do, because the ui gains and
    loses a hint line on an ordinary keypress rather than once at startup.
    It does not erase the block and lay it out again, which shows as a
    blank frame. And it does not re-pin the block to the bottom of the
    screen, which would scroll everything above the ui up a line every
    time the cursor touched an enum field; the lines a shrinking block
    gives back are simply blanked where they stand, so growing back into
    them later costs no scroll at all.
    """
    if new == old:
        return ""
    if new > old:
        # A one line block is the line the cursor is already on, so the
        # first line of a new block costs nothing to scroll in.
        return "\n" * (new - max(old, 1))
    return (CLEAR_LINE + cursor_up(1)) * (old - new) + "\r"


def clip(line: str, width: int) -> str:
    """Keep a line inside the terminal without wrapping.

    Truncating a coloured string risks cutting an escape sequence in half,
    so an over-long line is stripped back to plain text first. Lines fit in
    the normal case and this never runs.
    """
    if visible_len(line) <= width:
        return line
    return ANSI.sub("", line)[:width]


class Terminal:
    """Raw-mode keyboard in, a fixed block of lines out."""

    def __init__(self, stream=None):
        self.out = stream or sys.stdout
        self.fd = sys.stdin.fileno()
        self._height = 0
        self._saved = None
        self._pending = b""

    def __enter__(self) -> "Terminal":
        self._saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)  # keys arrive unbuffered and unechoed
        self.out.write(HIDE_CURSOR)
        self.out.flush()
        return self

    def __exit__(self, *exc) -> None:
        # Park below the block so the shell prompt lands under the ui
        # rather than on top of it.
        self.out.write("\n" + SHOW_CURSOR)
        self.out.flush()
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self._saved)

    def draw(self, lines: list[str]) -> None:
        width = shutil.get_terminal_size().columns
        if len(lines) != self._height:
            self._reserve(len(lines))

        # The cursor always rests on the last line of the block, so going
        # back up by height-1 lands on the first.
        self.out.write(cursor_up(self._height - 1) + "\r")

        for i, line in enumerate(lines):
            self.out.write(CLEAR_LINE + clip(line, width))
            # No newline after the last line: that would scroll the block
            # off the bottom and we would chase it up the screen.
            self.out.write("\r\n" if i < len(lines) - 1 else "\r")
        self.out.flush()

    def _reserve(self, height: int) -> None:
        """Make the block `height` lines tall, in place."""
        self.out.write(resize(self._height, height))
        self._height = height

    def _fill(self, timeout: float) -> bool:
        """Wait for input and take everything that has arrived."""
        if not select.select([self.fd], [], [], timeout)[0]:
            return False
        self._pending += os.read(self.fd, 64)
        return True

    def key(self, timeout: float) -> str | None:
        """Next keystroke, or None if `timeout` passes with nothing typed.

        Reads straight from the fd rather than through sys.stdin: the text
        wrapper buffers ahead, and select() only ever sees the fd, so a
        buffered keystroke would sit there unnoticed until the next one
        arrived behind it.
        """
        if not self._pending and not self._fill(timeout):
            return None

        # An escape sequence lands in one burst; a bare Esc does not. Give
        # the rest of a sequence a moment to show up before calling it Esc.
        if self._pending == b"\x1b":
            self._fill(ESC_TIMEOUT)

        seq, self._pending = next_key(self._pending)
        return decode(seq)
