"""The ui, driven by keystrokes against a fake board. No terminal involved."""

import pytest

from fake_board import FakeBoard
from link import Link, LoopbackTransport
from protocol import Field
from sats_proto import Width
from theme import ANSI, GREEN, RED, Theme, visible_len
from tui import App

FIELDS = [
    Field("sleep_ms", 0, Width.WIDTH_U32),
    Field("temperature", 4, Width.WIDTH_F32),
    Field("board_power.voltage", 8, Width.WIDTH_F32),
    Field("mode", 16, Width.WIDTH_U8),
    Field("wrong", 13, Width.WIDTH_U32),  # misaligned, the board will refuse it
]


@pytest.fixture
def app():
    board = FakeBoard(size=20)
    board.poke(0, Width.WIDTH_U32, 250)
    board.poke(4, Width.WIDTH_F32, 36.5)
    app = App(FIELDS, Link(LoopbackTransport(board), timeout=0.05))
    app.board = board
    return app


def keys(app, *pressed):
    for key in pressed:
        app.handle_key(key)


def values(app):
    return {row.field.name: row.value for row in app.rows}


def test_refresh_shows_what_the_board_holds(app):
    app.refresh()
    assert values(app)["sleep_ms"] == "250"
    assert values(app)["temperature"] == "36.5"
    assert values(app)["board_power.voltage"] == "0"


def test_bad_offset_is_visible(app):
    """A field the board refuses must say so, not show a stale or blank value."""
    app.refresh()
    assert values(app)["wrong"] == "BAD_OFFSET"
    assert app.rows[-1].error
    assert "BAD_OFFSET" in "\n".join(app.render())


def test_vim_navigation(app):
    keys(app, "j", "j")
    assert app.cursor == 2
    keys(app, "k")
    assert app.cursor == 1
    keys(app, "G")
    assert app.cursor == len(FIELDS) - 1
    keys(app, "g")
    assert app.cursor == 0
    keys(app, "\x04")  # ctrl-d, half a screen down
    assert app.cursor == len(FIELDS) // 2
    keys(app, "\x15")  # ctrl-u
    assert app.cursor == 0
    keys(app, "k")  # clamped at the top
    assert app.cursor == 0


def test_arrow_keys_work_too(app):
    keys(app, "DOWN", "DOWN", "UP")
    assert app.cursor == 1


def test_write_selected_field(app):
    keys(app, "j", "j", "j")  # mode, a one byte field
    keys(app, "w", "0", "x", "a", "b", "ENTER")
    assert app.board.memory[16] == 0xAB
    assert values(app)["mode"] == "171"
    assert app.mode == "normal"


def test_write_reads_back_a_float(app):
    keys(app, "j", "w", "1", "2", ".", "5", "ENTER")
    assert app.board.peek(4, Width.WIDTH_F32) == 12.5
    assert values(app)["temperature"] == "12.5"


def test_escape_cancels_a_write(app):
    keys(app, "w", "9", "9", "ESC")
    assert app.board.peek(0, Width.WIDTH_U32) == 250  # untouched
    assert app.board.commands == []
    assert app.mode == "normal"
    assert app.buffer == ""


def test_backspace_edits_the_input(app):
    keys(app, "w", "1", "2", "3", "BACKSPACE", "ENTER")
    assert app.board.peek(0, Width.WIDTH_U32) == 12


def test_rejected_write_is_distinguishable_from_a_good_one(app):
    """The read back after a write is what makes the difference visible."""
    app.refresh()
    keys(app, "G")  # the misaligned field
    keys(app, "w", "1", "ENTER")
    assert values(app)["wrong"] == "BAD_OFFSET"
    assert "BAD_OFFSET" in app.message
    assert app.board.memory[13:17] == bytearray(4)


def test_bad_input_does_not_reach_the_board(app):
    keys(app, "w", "o", "o", "p", "s", "ENTER")
    assert app.board.commands == []
    assert "sleep_ms" in app.message


def test_out_of_range_input_is_refused(app):
    keys(app, "j", "j", "j", "w", "9", "9", "9", "ENTER")
    assert app.board.commands == []
    assert "uint8" in app.message


def test_colon_q_quits(app):
    keys(app, ":", "q", "ENTER")
    assert not app.running


def test_q_quits(app):
    keys(app, "q")
    assert not app.running


def test_colon_number_jumps_to_a_row(app):
    keys(app, ":", "3", "ENTER")
    assert app.cursor == 2


def test_unknown_colon_command_complains(app):
    keys(app, ":", "x", "ENTER")
    assert app.running
    assert "not a command" in app.message


def test_auto_refresh_polls_one_field_per_tick(app):
    """Spreading the poll over ticks is what keeps the ui responsive."""
    keys(app, "a")
    assert app.auto
    assert app.tick(now=1.0)
    assert values(app)["sleep_ms"] == "250"
    assert values(app)["temperature"] == "-", "only one field per tick"

    assert not app.tick(now=1.0), "not due yet"
    assert app.tick(now=99.0)
    assert values(app)["temperature"] == "36.5"

    keys(app, "a")
    assert not app.tick(now=1e6)


def test_render_has_a_row_per_field_and_a_cursor(app):
    lines = app.render()
    assert lines[1].split() == ["|", "field", "offset", "type", "value", "|"]
    assert lines[app.cursor_line].split()[1] == ">"
    keys(app, "j")
    assert app.render()[app.cursor_line].split()[:3] == ["|", ">", "temperature"]


def test_every_boxed_line_is_the_same_width(app):
    """Ragged borders are the most obvious way for this to look broken."""
    app.refresh()
    boxed = [line for line in app.render() if line.startswith(("+", "|"))]
    assert len(boxed) == len(app.rows) + 3  # top, header, rows, bottom
    assert len({visible_len(line) for line in boxed}) == 1


def test_the_footer_never_overhangs_the_box(app):
    """The box widens to fit the help line rather than the other way round."""
    box_width = visible_len(app.render()[0])
    assert visible_len(app.render()[-1]) <= box_width


def test_colour_does_not_disturb_the_layout(app):
    """Escape codes have width in a format string but none on screen."""
    app.refresh()
    plain = app.render()
    app.theme = Theme(color=True, unicode=False)
    coloured = app.render()

    assert coloured != plain  # colour really is on
    assert [visible_len(line) for line in coloured] == [
        visible_len(line) for line in plain
    ]
    assert [ANSI.sub("", line) for line in coloured] == plain


def test_a_refused_field_is_marked_as_an_error(app):
    app.refresh()
    row = {r.field.name: r for r in app.rows}["wrong"]  # misaligned offset
    assert row.error
    app.theme = Theme(color=True, unicode=False)
    line = [line for line in app.render() if "wrong" in ANSI.sub("", line)][0]
    assert RED in line


# -- enums ---------------------------------------------------------------

MODE = Field(
    "mode",
    16,
    Width.WIDTH_U8,
    enumerators=((0, "BOOT"), (1, "NOMINAL"), (2, "SAFE")),
    type_label="enum Mode",
)

ENUM_FIELDS = [Field("sleep_ms", 0, Width.WIDTH_U32), MODE]


@pytest.fixture
def enum_app():
    board = FakeBoard(size=20)
    board.poke(16, Width.WIDTH_U8, 1)  # NOMINAL
    app = App(ENUM_FIELDS, Link(LoopbackTransport(board), timeout=0.05))
    app.board = board
    return app


def hint(app):
    """The hint line, which sits just under the box when there is one."""
    lines = app.render()
    below = max(i for i, line in enumerate(lines) if line.startswith("+")) + 1
    # Under the box comes the hint if there is one, then the prompt and
    # the footer; two lines left over means this row has no hint.
    return lines[below].strip() if len(lines) - below == 3 else ""


def test_an_enum_reads_back_as_its_name(enum_app):
    enum_app.refresh()
    assert values(enum_app)["mode"] == "NOMINAL"
    assert "NOMINAL" in "\n".join(enum_app.render())


def test_an_enum_can_be_written_by_name(enum_app):
    keys(enum_app, "j", "w", "S", "A", "F", "E", "ENTER")
    assert enum_app.board.memory[16] == 2, "the name went out as the number"
    assert values(enum_app)["mode"] == "SAFE"
    assert enum_app.mode == "normal"


def test_an_enum_can_still_be_written_by_number(enum_app):
    keys(enum_app, "j", "w", "0", "ENTER")
    assert enum_app.board.memory[16] == 0
    assert values(enum_app)["mode"] == "BOOT"


def test_a_bad_enum_name_does_not_reach_the_board(enum_app):
    keys(enum_app, "j", "w", "N", "O", "P", "E", "ENTER")
    assert enum_app.board.commands == []
    assert "NOMINAL" in enum_app.message, "the message says what would have worked"


def test_a_value_no_enumerator_claims_is_flagged(enum_app):
    """A slate mode of 7 is a bug, and the ui should not launder it."""
    enum_app.board.poke(16, Width.WIDTH_U8, 7)
    enum_app.refresh()
    assert values(enum_app)["mode"] == "7?"


def test_the_hint_lists_the_options_for_the_selected_enum(enum_app):
    enum_app.refresh()
    assert hint(enum_app) == "", "sleep_ms is not an enum, so no hint"
    keys(enum_app, "j")
    options = ["0", "BOOT", "-", "1", "NOMINAL", "-", "2", "SAFE"]
    assert hint(enum_app).split() == options


def test_the_hint_is_up_while_the_value_is_being_typed(enum_app):
    keys(enum_app, "j", "w", "S")
    assert "SAFE" in hint(enum_app)
    assert enum_app.prompt() == "mode = S"


def test_the_hint_marks_the_current_value(enum_app):
    enum_app.refresh()
    keys(enum_app, "j")
    enum_app.theme = Theme(color=True, unicode=False)
    line = [ln for ln in enum_app.render() if "NOMINAL" in ANSI.sub("", ln)][0]
    assert GREEN in line  # the value it is sitting on, picked out of the list


def test_the_hint_never_overhangs_the_box(enum_app):
    """A long enum has to give up options rather than ragged edges."""
    wide = Field(
        "mode",
        16,
        Width.WIDTH_U8,
        enumerators=tuple((i, f"STATE_NUMBER_{i}") for i in range(12)),
        type_label="enum Mode",
    )
    app = App([wide], Link(LoopbackTransport(FakeBoard(size=20)), timeout=0.05))
    app.refresh()
    box_width = visible_len(app.render()[0])
    assert all(visible_len(line) <= box_width for line in app.render())
    assert "..." in hint(app), "the list was cut short"


def test_enum_names_do_not_ragged_the_box(enum_app):
    """The value column is sized for the names it may have to show."""
    enum_app.refresh()
    keys(enum_app, "j", "w", "S", "A", "F", "E", "ENTER")  # the longest name
    boxed = [line for line in enum_app.render() if line.startswith(("+", "|"))]
    assert len({visible_len(line) for line in boxed}) == 1


def test_prompt_shows_what_is_being_typed(app):
    keys(app, "w", "4", "2")
    assert app.prompt() == "sleep_ms = 42"
    keys(app, "ESC", ":", "q")
    assert app.prompt() == ":q"
