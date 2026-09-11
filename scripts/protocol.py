#!/usr/bin/env python3
"""
protocol.py - slate fields, and the SatCmds that address them.

Pure translation between what the debug info says a slate field is and what
the contract says about it. No I/O lives here, so it can be tested against
the fake board without a port or a terminal.
"""

from dataclasses import dataclass

from sats_proto import SatCmd, Status, Width

WIDTH_BYTES = {
    Width.WIDTH_U8: 1,
    Width.WIDTH_U16: 2,
    Width.WIDTH_U32: 4,
    Width.WIDTH_F32: 4,
}

WIDTH_NAMES = {
    Width.WIDTH_U8: "uint8",
    Width.WIDTH_U16: "uint16",
    Width.WIDTH_U32: "uint32",
    Width.WIDTH_F32: "float",
}


class Unsupported(Exception):
    """A slate member the command set has no width for."""


@dataclass(frozen=True)
class Field:
    """One individually addressable slate member."""

    name: str
    offset: int
    width: int  # a Width enum value

    @property
    def size(self) -> int:
        return WIDTH_BYTES[self.width]

    @property
    def type_name(self) -> str:
        return WIDTH_NAMES[self.width]

    @property
    def is_float(self) -> bool:
        return self.width == Width.WIDTH_F32


def width_of(member: dict) -> int:
    """Pick the command width for a member of a parse_slate layout.

    Everything the contract can address is 1, 2 or 4 bytes wide; a float is
    the only thing that is not just raw bits, and only the debug info knows
    which of the two a 4 byte member is.
    """
    size, type_name = member.get("size"), member.get("type", "")
    if "float" in type_name and size == 4:
        return Width.WIDTH_F32
    for width, width_size in ((Width.WIDTH_U8, 1), (Width.WIDTH_U16, 2), (Width.WIDTH_U32, 4)):
        if size == width_size:
            return width
    raise Unsupported(f"no command width for a {size} byte {type_name or '?'}")


def fields_from_layout(layout: dict) -> tuple[list[Field], dict[str, str]]:
    """Split a parse_slate layout into addressable fields and the leftovers."""
    fields, skipped = [], {}
    for name, member in layout.items():
        try:
            fields.append(Field(name, member["offset"], width_of(member)))
        except Unsupported as err:
            skipped[name] = str(err)
    return fields, skipped


def read_cmd(field: Field) -> SatCmd:
    cmd = SatCmd()
    cmd.read.offset = field.offset
    cmd.read.width = field.width
    return cmd


def write_cmd(field: Field, value) -> SatCmd:
    """A write of `value` to `field`, as the variant matching its width."""
    cmd = SatCmd()
    if field.is_float:
        cmd.write_f32.offset = field.offset
        cmd.write_f32.value = float(value)
        return cmd

    limit = (1 << (8 * field.size)) - 1
    if not 0 <= value <= limit:
        raise ValueError(f"{value} does not fit in a {field.type_name}")
    write = {
        Width.WIDTH_U8: cmd.write_u8,
        Width.WIDTH_U16: cmd.write_u16,
        Width.WIDTH_U32: cmd.write_u32,
    }[field.width]
    write.offset = field.offset
    write.value = value
    return cmd


def parse_value(text: str, field: Field):
    """Turn typed input into a value for write_cmd().

    Python's own conversion errors read like a stack trace escaped into
    the ui, so they are restated in terms of the field being written.
    """
    text = text.strip()
    if not text:
        raise ValueError("no value given")

    try:
        if field.is_float:
            return float(text)
        value = int(text, 0)  # base 0, so 0x20 and 0b101 work too
    except ValueError:
        raise ValueError(f"{text!r} is not a {field.type_name}") from None

    limit = (1 << (8 * field.size)) - 1
    if not 0 <= value <= limit:
        raise ValueError(f"{value} does not fit in a {field.type_name}")
    return value


def response_value(response):
    """The value carried by a SatResponse, or None if it carries neither."""
    which = response.WhichOneof("value")
    return None if which is None else getattr(response, which)


def format_value(response) -> str:
    """How a reply should read in the table: the value, or why there isn't one."""
    if response is None:
        return "no reply"
    if response.status != Status.STATUS_OK:
        return Status.Name(response.status).removeprefix("STATUS_")

    value = response_value(response)
    if value is None:
        return "no value"
    if response.width == Width.WIDTH_F32:
        return f"{value:g}"
    return str(value)
