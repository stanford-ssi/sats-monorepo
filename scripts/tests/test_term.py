"""The terminal driver's pure parts: key decoding and line clipping."""

import pytest

from term import clip, decode, next_key
from theme import Theme, visible_len

CASES = [
    ("j", "j"),
    (":", ":"),
    ("\x1b", "ESC"),  # a lone esc, not the start of a sequence
    ("\x1b[A", "UP"),
    ("\x1b[B", "DOWN"),
    ("\x1b[H", "HOME"),
    ("\x1b[F", "END"),
    ("\x1b[5~", "PGUP"),
    ("\x1b[6~", "PGDN"),
    ("\r", "ENTER"),
    ("\n", "ENTER"),
    ("\x7f", "BACKSPACE"),
    ("\x08", "BACKSPACE"),
    ("\x04", "\x04"),  # ctrl-d, App reads it raw
    ("\x03", "q"),  # ctrl-c quits instead of raising
    ("", None),
    ("\x1b[Z", None),  # shift-tab, nothing is bound to it
]


@pytest.mark.parametrize("seq,expected", CASES)
def test_decode(seq, expected):
    assert decode(seq) == expected


def test_clip_leaves_a_fitting_line_alone():
    line = Theme()("hello", "1")
    assert clip(line, 20) == line


def test_clip_measures_what_is_visible_not_what_is_stored():
    """A coloured line is longer in bytes than on screen; only the screen
    width should decide whether it needs cutting."""
    line = Theme()("hello", "1")
    assert len(line) > 10 and visible_len(line) == 5
    assert clip(line, 5) == line


def test_clip_strips_colour_before_truncating():
    """Cutting mid escape sequence would leave the terminal stuck in a
    colour, so an over-long line loses its styling instead."""
    out = clip(Theme()("hello world", "1"), 5)
    assert out == "hello"
    assert "\x1b" not in out


SPLITS = [
    (b"jj", "j", b"j"),  # two keys in one read
    (b"w137\r", "w", b"137\r"),  # a whole typed value at once
    (b"\x1b[A", "\x1b[A", b""),
    (b"\x1b[Aj", "\x1b[A", b"j"),  # a sequence followed by a key
    (b"\x1b[5~k", "\x1b[5~", b"k"),
    (b"\x1b", "\x1b", b""),
    (b"\xc3\xa9x", "é", b"x"),  # utf-8 stays in one piece
]


@pytest.mark.parametrize("pending,key,rest", SPLITS)
def test_next_key_splits_one_keystroke_off(pending, key, rest):
    assert next_key(pending) == (key, rest)


def test_a_burst_of_keys_all_come_out_in_order():
    """The bug this guards: reading one byte at a time through a buffered
    stream leaves the rest invisible to select(), so keys arrive a
    keystroke late."""
    pending, got = b"jjw42\r", []
    while pending:
        seq, pending = next_key(pending)
        got.append(decode(seq))
    assert got == ["j", "j", "w", "4", "2", "ENTER"]
