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
    Width.WIDTH_BOOL: 1,
    Width.WIDTH_I8: 1,
    Width.WIDTH_I16: 2,
    Width.WIDTH_I32: 4,
}

WIDTH_NAMES = {
    Width.WIDTH_U8: "uint8",
    Width.WIDTH_U16: "uint16",
    Width.WIDTH_U32: "uint32",
    Width.WIDTH_F32: "float",
    Width.WIDTH_BOOL: "bool",
    Width.WIDTH_I8: "int8",
    Width.WIDTH_I16: "int16",
    Width.WIDTH_I32: "int32",
}

SIGNED = (Width.WIDTH_I8, Width.WIDTH_I16, Width.WIDTH_I32)

# DW_ATE_* from the DWARF spec. The debug info says outright whether a
# member is signed, unsigned, float or boolean, which beats inferring it
# from how the type happens to be spelled.
DW_ATE_BOOLEAN = 0x02
DW_ATE_FLOAT = 0x04
DW_ATE_SIGNED = 0x05
DW_ATE_SIGNED_CHAR = 0x06
DW_ATE_UNSIGNED = 0x07
DW_ATE_UNSIGNED_CHAR = 0x08

WIDTH_BY_ENCODING = {
    (DW_ATE_BOOLEAN, 1): Width.WIDTH_BOOL,
    (DW_ATE_FLOAT, 4): Width.WIDTH_F32,
    (DW_ATE_SIGNED, 1): Width.WIDTH_I8,
    (DW_ATE_SIGNED_CHAR, 1): Width.WIDTH_I8,
    (DW_ATE_SIGNED, 2): Width.WIDTH_I16,
    (DW_ATE_SIGNED, 4): Width.WIDTH_I32,
    (DW_ATE_UNSIGNED, 1): Width.WIDTH_U8,
    (DW_ATE_UNSIGNED_CHAR, 1): Width.WIDTH_U8,
    (DW_ATE_UNSIGNED, 2): Width.WIDTH_U16,
    (DW_ATE_UNSIGNED, 4): Width.WIDTH_U32,
}


# What a human might reasonably type for a bool. `2` is not on the list on
# purpose: a slate bool that is neither true nor false is a bug worth
# seeing rather than something to accept silently.
BOOL_WORDS = {
    "true": True,
    "false": False,
    "1": True,
    "0": False,
    "on": True,
    "off": False,
    "yes": True,
    "no": False,
    "t": True,
    "f": False,
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

    @property
    def is_bool(self) -> bool:
        return self.width == Width.WIDTH_BOOL

    @property
    def is_signed(self) -> bool:
        return self.width in SIGNED

    @property
    def limits(self) -> tuple[int, int]:
        """Inclusive range an integer field accepts."""
        bits = 8 * self.size
        if self.is_signed:
            return -(1 << (bits - 1)), (1 << (bits - 1)) - 1
        return 0, (1 << bits) - 1


# Spellings to fall back on when a layout carries no encoding, e.g. one
# built by hand in a test.
NAMED_WIDTHS = {
    ("bool", 1): Width.WIDTH_BOOL,
    ("_Bool", 1): Width.WIDTH_BOOL,
    ("float", 4): Width.WIDTH_F32,
    ("int8_t", 1): Width.WIDTH_I8,
    ("signed char", 1): Width.WIDTH_I8,
    ("int16_t", 2): Width.WIDTH_I16,
    ("short int", 2): Width.WIDTH_I16,
    ("int32_t", 4): Width.WIDTH_I32,
    ("int", 4): Width.WIDTH_I32,
}


def width_of(member: dict) -> int:
    """Pick the command width for a member of a parse_slate layout.

    Size alone is not enough: at one byte a uint8, an int8 and a bool are
    indistinguishable, and at four a uint32, an int32 and a float are. So
    this leans on DW_AT_encoding, which states which it is, and only falls
    back to the type's spelling when a layout has no encoding.
    """
    size, type_name = member.get("size"), member.get("type", "")
    encoding = member.get("encoding")

    width = WIDTH_BY_ENCODING.get((encoding, size))
    if width is not None:
        return width

    width = NAMED_WIDTHS.get((type_name, size))
    if width is not None:
        return width

    # Unsigned is the safe assumption for an unlabelled integer: it is how
    # the raw bytes read, and nothing is silently sign extended.
    if encoding is None and size in (1, 2, 4) and "[" not in type_name:
        return {1: Width.WIDTH_U8, 2: Width.WIDTH_U16, 4: Width.WIDTH_U32}[size]

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
    if field.is_bool:
        cmd.write_bool.offset = field.offset
        cmd.write_bool.value = bool(value)
        return cmd

    if field.is_float:
        cmd.write_f32.offset = field.offset
        cmd.write_f32.value = float(value)
        return cmd

    low, high = field.limits
    if not low <= value <= high:
        raise ValueError(f"{value} does not fit in a {field.type_name}")
    write = {
        Width.WIDTH_U8: cmd.write_u8,
        Width.WIDTH_U16: cmd.write_u16,
        Width.WIDTH_U32: cmd.write_u32,
        Width.WIDTH_I8: cmd.write_i8,
        Width.WIDTH_I16: cmd.write_i16,
        Width.WIDTH_I32: cmd.write_i32,
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

    if field.is_bool:
        try:
            return BOOL_WORDS[text.lower()]
        except KeyError:
            raise ValueError(f"{text!r} is not a bool (try true or false)") from None

    try:
        if field.is_float:
            return float(text)
        value = int(text, 0)  # base 0, so 0x20 and 0b101 work too
    except ValueError:
        raise ValueError(f"{text!r} is not a {field.type_name}") from None

    low, high = field.limits
    if not low <= value <= high:
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
    if response.width == Width.WIDTH_BOOL:
        return "true" if value else "false"
    if response.width == Width.WIDTH_F32:
        return f"{value:g}"
    return str(value)
