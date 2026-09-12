#!/usr/bin/env python3
"""
tui.py - the slate browser.

App is the whole ui as a state machine: keys in, lines out, and a Link for
the round trips. It does no io of its own, which is what makes it testable
against the fake board. The driver at the bottom only feeds it keystrokes
and hands its lines to the terminal.
"""

import time
from dataclasses import dataclass

import term
import theme as th
from protocol import Field, format_value, parse_value, read_cmd, write_cmd
from sats_proto import Status

# Seconds between auto refresh round trips. One field is polled per tick
# rather than the whole table, so a slow or absent board cannot stall the ui.
AUTO_STEP = 0.15

HELP = (
    ("w", "write"),
    ("r", "refresh"),
    ("a", "auto"),
    ("j/k", "move"),
    ("g/G", "ends"),
    ("q", "quit"),
)

VALUE_W = 11


@dataclass
class Row:
    """One slate field and the last thing the board said about it."""

    field: Field
    value: str = "-"
    error: bool = False

    def update(self, response) -> None:
        self.value = format_value(response, self.field)
        self.error = response is None or response.status != Status.STATUS_OK


class App:
    """The ui as a state machine: keys in, lines out, round trips in between."""

    def __init__(self, fields: list, link, theme=None, title="Slate", subtitle=""):
        self.link = link
        self.theme = theme or th.PLAIN
        self.title = title
        self.subtitle = subtitle
        self.rows = [Row(f) for f in fields]
        self.cursor = 0
        self.mode = "normal"  # "write" and "command" both take a line of input
        self.buffer = ""
        self.message = ""
        self.auto = False
        self.running = True
        self._auto_next = 0.0
        self._auto_row = 0

    # -- state ---------------------------------------------------------

    @property
    def row(self) -> Row:
        return self.rows[self.cursor]

    def move(self, delta: int) -> None:
        self.cursor = max(0, min(len(self.rows) - 1, self.cursor + delta))

    def refresh(self) -> None:
        """Re-read every field from the board."""
        for row in self.rows:
            self.refresh_row(row)
        self.message = "refreshed"

    def refresh_row(self, row: Row) -> None:
        row.update(self.link.request(read_cmd(row.field)))

    def tick(self, now: float) -> bool:
        """Poll one field if auto refresh is due. Returns True if it did."""
        if not self.auto or now < self._auto_next:
            return False
        self._auto_next = now + AUTO_STEP
        self._auto_row %= len(self.rows)
        self.refresh_row(self.rows[self._auto_row])
        self._auto_row += 1
        return True

    def write(self, text: str) -> None:
        """Write typed input to the selected field and show what landed."""
        row = self.row
        try:
            cmd = write_cmd(row.field, parse_value(text, row.field))
        except ValueError as err:
            self.message = f"{row.field.name}: {err}"
            return

        response = self.link.request(cmd)
        # Read it straight back, so a rejected write shows the old value
        # rather than the value that was asked for.
        self.refresh_row(row)
        self.message = f"{row.field.name} <- {format_value(response, row.field)}"

    # -- keys ----------------------------------------------------------

    def handle_key(self, key: str) -> None:
        if self.mode == "normal":
            self._normal_key(key)
        else:
            self._input_key(key)

    def _normal_key(self, key: str) -> None:
        if key in ("j", "DOWN"):
            self.move(1)
        elif key in ("k", "UP"):
            self.move(-1)
        elif key in ("g", "HOME"):
            self.cursor = 0
        elif key in ("G", "END"):
            self.cursor = len(self.rows) - 1
        elif key in ("\x04", "PGDN"):  # ctrl-d
            self.move(max(1, len(self.rows) // 2))
        elif key in ("\x15", "PGUP"):  # ctrl-u
            self.move(-max(1, len(self.rows) // 2))
        elif key in ("w", "i", "ENTER"):
            self.mode = "write"
            self.buffer = ""
        elif key == "r":
            self.refresh()
        elif key == "a":
            self.auto = not self.auto
            self._auto_next = 0.0
            self.message = f"auto refresh {'on' if self.auto else 'off'}"
        elif key == ":":
            self.mode = "command"
            self.buffer = ""
        elif key == "q":
            self.running = False

    def _input_key(self, key: str) -> None:
        """Line editing for the write and : prompts."""
        if key == "ESC":
            self.mode, self.buffer, self.message = "normal", "", "cancelled"
        elif key == "BACKSPACE":
            self.buffer = self.buffer[:-1]
        elif key == "ENTER":
            text, mode = self.buffer, self.mode
            self.mode, self.buffer = "normal", ""
            if mode == "write":
                self.write(text)
            else:
                self._command(text)
        elif len(key) == 1 and key.isprintable():
            self.buffer += key

    def _command(self, text: str) -> None:
        """The handful of : commands a vim user will try."""
        text = text.strip()
        if text in ("q", "q!", "quit"):
            self.running = False
        elif text.isdigit():  # :42 jumps to a row, as in vim
            self.cursor = max(0, min(len(self.rows) - 1, int(text) - 1))
        elif text:
            self.message = f"not a command: :{text}"

    # -- rendering -----------------------------------------------------

    @property
    def cursor_line(self) -> int:
        """Index into render()'s output of the selected row."""
        return 2 + self.cursor  # top border, then the header

    def prompt(self) -> str:
        if self.mode == "write":
            return f"{self.row.field.name} = {self.buffer}"
        if self.mode == "command":
            return f":{self.buffer}"
        return self.message

    def _value_floor(self) -> int:
        """Widest the value column ever needs to be.

        Sized from the fields rather than from the values they happen to
        hold, so the box does not jitter a column wider the first time a
        long enumerator name comes back from the board.
        """
        widest = [VALUE_W]
        for row in self.rows:
            field = row.field
            if field.is_enum:
                widest += [len(name) for _, name in field.enumerators]
                # Room for the `7?` an unclaimed value shows as.
                widest += [len(str(limit)) + 1 for limit in field.limits]
        return max(widest)

    def _widths(self) -> tuple[int, int, int]:
        """Column widths, with any slack given to the value column.

        The box is widened to fit the footer, and the spare width goes
        between `type` and `value` so the numbers stay flush against the
        right edge instead of trailing off into padding.
        """
        name_w = max([5] + [len(r.field.name) for r in self.rows])
        type_w = max([4] + [len(r.field.type_name) for r in self.rows])
        value_w = self._value_floor()
        natural = 3 + name_w + 8 + 2 + type_w + 2 + value_w + 1
        slack = max(0, th.visible_len(self._help_text()) - natural)
        return name_w, type_w, value_w + slack

    def _cells(self, marker, name, offset, type_name, value) -> list[str]:
        """One row's cells, padded to their columns.

        Padding happens before any colour goes on: an escape sequence has
        no width on screen but plenty in a format string, so styling first
        would throw every column out of line.
        """
        name_w, type_w, value_w = self._widths()
        return [
            f" {marker} ",
            f"{name:<{name_w}}",
            f"  {offset:>6}",
            f"  {type_name:<{type_w}}",
            f"  {value:>{value_w}} ",
        ]

    def _inner_width(self) -> int:
        return sum(len(c) for c in self._cells(" ", "", "", "", ""))

    def _framed(self, body: str) -> str:
        """Put a row of content between the box sides, padded to width."""
        t = self.theme
        pad = " " * max(0, self._inner_width() - th.visible_len(body))
        return t(t.box["v"], th.DIM) + body + pad + t(t.box["v"], th.DIM)

    def _bottom_bar(self) -> str:
        t = self.theme
        return t(t.box["bl"] + t.box["h"] * self._inner_width() + t.box["br"], th.DIM)

    def _title_bar(self) -> str:
        t = self.theme
        h = t.box["h"]
        title = t(self.title, th.BOLD)
        subtitle = t(self.subtitle, th.DIM) if self.subtitle else ""
        left = t(t.box["tl"] + h + " ", th.DIM) + title + t(" ", th.DIM)
        right = ((t(" ", th.DIM) + subtitle + t(" ", th.DIM)) if subtitle else "") + t(
            h + t.box["tr"], th.DIM
        )
        fill = self._inner_width() - th.visible_len(left) - th.visible_len(right) + 2
        return left + t(h * max(0, fill), th.DIM) + right

    def _row_line(self, i: int, row: "Row") -> str:
        t = self.theme
        selected = i == self.cursor
        marker = t(t.marker, th.CYAN, th.BOLD) if selected else " "
        cells = self._cells(
            marker, row.field.name, row.field.offset, row.field.type_name, row.value
        )

        if row.error:
            value = t(cells[4], th.RED, th.BOLD)
        elif row.value == "-":
            value = t(cells[4], th.DIM)
        else:
            value = t(cells[4], th.GREEN)

        name = t(cells[1], th.BOLD) if selected else cells[1]
        return self._framed(
            cells[0] + name + t(cells[2], th.DIM) + t(cells[3], th.DIM) + value
        )

    def _header_line(self) -> str:
        cells = self._cells(" ", "field", "offset", "type", "value")
        return self._framed(self.theme("".join(cells), th.DIM))

    def _prompt_line(self) -> str:
        t = self.theme
        if self.mode == "write":
            return (
                "  "
                + t(self.row.field.name, th.BOLD)
                + t(" = ", th.DIM)
                + self.buffer
                + t(t.caret, th.CYAN)
            )
        if self.mode == "command":
            return "  " + t(":", th.DIM) + self.buffer + t(t.caret, th.CYAN)
        if not self.message:
            return ""
        colour = th.RED if self.row.error else th.DIM
        return "  " + t(self.message, colour)

    def _hint_line(self) -> str:
        """What the selected enum will accept, since the names are not guessable.

        Only enums get one: every other width says everything it accepts in
        its type, and a line that is empty most of the time is a line the
        table could have used instead.
        """
        field = self.row.field
        if not field.is_enum:
            return ""

        t = self.theme
        sep = t(f" {t.sep} ", th.DIM)
        options = [f"{value} {name}" for value, name in field.enumerators]

        # How many options fit, counting the ellipsis that stands in for
        # the ones that do not. A ragged line past the edge of the box
        # looks broken, and this is a hint, not something to scroll.
        room = self._inner_width()  # a box line is the indent plus a border
        widths = th.visible_len(sep), len(t.ellipsis)

        def length(count: int) -> int:
            items = options[:count] + ([t.ellipsis] if count < len(options) else [])
            return sum(map(len, items)) + widths[0] * max(0, len(items) - 1)

        fits = len(options)
        while fits and length(fits) > room:
            fits -= 1

        shown = []
        for value, name in field.enumerators[:fits]:
            # The value it is currently sitting on is worth picking out of
            # the list, so the table and the hint read as the same thing.
            style = (th.GREEN, th.BOLD) if name == self.row.value else (th.DIM,)
            shown.append(t(str(value), th.DIM) + " " + t(name, *style))
        if fits < len(options):
            shown.append(t(t.ellipsis, th.DIM))
        return "  " + sep.join(shown)

    def _help_text(self) -> str:
        t = self.theme
        parts = [t(key, th.CYAN) + " " + t(label, th.DIM) for key, label in HELP]
        return t(f" {t.sep} ", th.DIM).join(parts)

    def _help_line(self) -> str:
        return "  " + self._help_text()

    def render(self) -> list[str]:
        """The whole ui, one string per terminal line."""
        lines = [self._title_bar(), self._header_line()]
        lines += [self._row_line(i, row) for i, row in enumerate(self.rows)]
        lines.append(self._bottom_bar())
        if hint := self._hint_line():
            lines.append(hint)
        lines += [self._prompt_line(), self._help_line()]
        return lines


# -- driver --------------------------------------------------------------


def run(app: App, screen: term.Terminal) -> None:
    app.refresh()
    dirty = True
    while app.running:
        if dirty:  # only repaint when something actually moved
            screen.draw(app.render())
        key = screen.key(AUTO_STEP / 3)  # never block long on input
        if key is not None:
            app.handle_key(key)
        dirty = key is not None
        dirty |= app.tick(time.monotonic())


def main(app: App) -> None:
    with term.Terminal() as screen:
        run(app, screen)
