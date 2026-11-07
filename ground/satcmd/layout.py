"""
layout.py - what the bytes of a slate mean, read from the firmware elf.

The protocol only moves raw bytes, so this is the one place in the whole
system that knows about types. Every leaf of the slate struct becomes a
Field, with its offset and width taken from the DWARF debug info and its
interpretation (unsigned, signed, float or bool) from DW_AT_encoding, which
says outright what a type is rather than leaving it to be guessed from how
it happens to be spelled.

Nested structs are flattened to dotted names (`board_power.voltage`) and
arrays to indexed ones (`samples[3]`), since every leaf is separately
addressable.
"""

import difflib
import math
import struct
from dataclasses import dataclass, field

from elftools.dwarf.die import DIE
from elftools.elf.elffile import ELFFile

from satcmd.proto import WIDTHS

# DW_ATE_* from the DWARF spec.
DW_ATE_BOOLEAN = 0x02
DW_ATE_FLOAT = 0x04
DW_ATE_SIGNED = 0x05
DW_ATE_SIGNED_CHAR = 0x06
DW_ATE_UNSIGNED = 0x07
DW_ATE_UNSIGNED_CHAR = 0x08
DW_ATE_UTF = 0x10

KIND_BY_ENCODING = {
    DW_ATE_BOOLEAN: "bool",
    DW_ATE_FLOAT: "float",
    DW_ATE_SIGNED: "int",
    DW_ATE_SIGNED_CHAR: "int",
    DW_ATE_UNSIGNED: "uint",
    DW_ATE_UNSIGNED_CHAR: "uint",
    DW_ATE_UTF: "uint",
}

FLOAT_FORMATS = {4: "<f"}  # the protocol tops out at 32 bits

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
}

QUALIFIERS = ("DW_TAG_typedef", "DW_TAG_const_type", "DW_TAG_volatile_type")
AGGREGATES = ("DW_TAG_structure_type", "DW_TAG_class_type", "DW_TAG_union_type")


@dataclass(frozen=True)
class Field:
    """One addressable leaf of the slate, and how to read its bytes."""

    name: str
    offset: int
    width: int  # bytes
    kind: str  # "uint", "int", "float" or "bool"
    type_name: str = ""  # the c spelling, for display only

    def __post_init__(self):
        if self.width not in WIDTHS:
            raise ValueError(f"{self.name}: no {self.width} byte width")
        if self.kind == "float" and self.width not in FLOAT_FORMATS:
            raise ValueError(f"{self.name}: no {self.width} byte float")
        if self.kind == "bool" and self.width != 1:
            raise ValueError(f"{self.name}: a bool is one byte")

    @property
    def limits(self) -> tuple[int, int]:
        """Inclusive range of an integer field."""
        bits = 8 * self.width
        if self.kind == "int":
            return -(1 << (bits - 1)), (1 << (bits - 1)) - 1
        return 0, (1 << bits) - 1

    def encode(self, value) -> int:
        """A python value as the raw unsigned integer that goes on the wire.

        Refuses anything that does not fit rather than letting the board
        truncate it, so what you write is what you meant.
        """
        if self.kind == "bool":
            if value not in (True, False):  # 0 and 1 compare equal, so pass
                raise ValueError(f"{self.name}: {value!r} is not a bool")
            return int(bool(value))

        if self.kind == "float":
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise TypeError(f"{self.name}: {value!r} is not a number")
            try:
                raw = struct.pack(FLOAT_FORMATS[self.width], value)
            except OverflowError:
                raise ValueError(
                    f"{self.name}: {value} does not fit in a float"
                ) from None
            return int.from_bytes(raw, "little")

        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{self.name}: {value!r} is not an integer")
        low, high = self.limits
        if not low <= value <= high:
            raise ValueError(f"{self.name}: {value} does not fit in {self._spelling}")
        return value & ((1 << (8 * self.width)) - 1)  # two's complement

    def decode(self, raw: int):
        """The raw unsigned integer off the wire as a python value."""
        if self.kind == "bool":
            return raw != 0  # any non zero byte, as c++ would read it
        if self.kind == "float":
            data = raw.to_bytes(self.width, "little")
            value = struct.unpack(FLOAT_FORMATS[self.width], data)[0]
            return _shortest_f32(value, data)
        if self.kind == "int" and raw >= 1 << (8 * self.width - 1):
            return raw - (1 << (8 * self.width))
        return raw

    def parse(self, text: str):
        """Typed input from a human, as a value for encode()."""
        text = text.strip()
        if not text:
            raise ValueError("no value given")
        if self.kind == "bool":
            try:
                return BOOL_WORDS[text.lower()]
            except KeyError:
                raise ValueError(
                    f"{text!r} is not a bool (try true or false)"
                ) from None
        try:
            if self.kind == "float":
                return float(text)
            return int(text, 0)  # base 0, so 0x20 and 0b101 work too
        except ValueError:
            raise ValueError(f"{text!r} is not {self._spelling}") from None

    def format(self, value) -> str:
        """A value as it should read on screen."""
        if self.kind == "bool":
            return "true" if value else "false"
        if self.kind == "float":
            return f"{value:.7g}"
        return str(value)

    @property
    def _spelling(self) -> str:
        return self.type_name or f"a {self.width} byte {self.kind}"


def _shortest_f32(value: float, data: bytes) -> float:
    """The shortest decimal that is still exactly this float32.

    A float32 widened to a python float drags its rounding error along:
    write 3.3 and you read back 3.299999952316284, so `== 3.3` fails even
    though the board holds exactly the float32 nearest 3.3. Returning the
    shortest decimal that packs back to the same bits gives 3.3 instead.
    Nothing is lost: writing the result back stores identical bits.
    """
    if not math.isfinite(value):
        return value
    for digits in range(1, 10):  # 9 significant digits always suffice
        candidate = float(f"{value:.{digits}g}")
        try:
            if struct.pack("<f", candidate) == data:
                return candidate
        except OverflowError:
            pass  # rounding up near FLT_MAX can step past it
    return value


@dataclass
class Layout:
    """Every addressable field of a struct, plus whatever could not be."""

    name: str
    size: int
    fields: list[Field]
    skipped: dict[str, str] = field(default_factory=dict)  # name -> why

    def __post_init__(self):
        self._by_name = {f.name: f for f in self.fields}

    def __getitem__(self, name: str) -> Field:
        try:
            return self._by_name[name]
        except KeyError:
            raise KeyError(self.unknown(name)) from None

    def __contains__(self, name: str) -> bool:
        return name in self._by_name

    def unknown(self, name: str) -> str:
        """An error message for a name that is not a field, with a hint."""
        message = f"no field {name!r} in {self.name}"
        if name in self.skipped:
            return f"{message} ({self.skipped[name]})"
        close = difflib.get_close_matches(name, self._by_name, n=1)
        return f"{message}, did you mean {close[0]!r}?" if close else message


def load(elf_path: str, struct_name: str = "Slate") -> Layout:
    """The layout of `struct_name`, from an elf built with debug info."""
    with open(elf_path, "rb") as f:
        elf = ELFFile(f)
        if not elf.has_dwarf_info():
            raise ValueError(f"{elf_path} has no debug info (build with -g)")
        die = _find_struct(elf.get_dwarf_info(), struct_name)
        if die is None:
            raise ValueError(f"struct {struct_name!r} not found in {elf_path}")

        fields, skipped = [], {}
        for name, offset, type_die in _leaves(die, "", 0):
            try:
                fields.append(_field(name, offset, type_die))
            except ValueError as err:
                skipped[name] = str(err)
        size = die.attributes["DW_AT_byte_size"].value

    return Layout(struct_name, size, fields, skipped)


def _find_struct(dwarf, struct_name: str) -> DIE | None:
    """The first full definition of a struct by that name, at any depth."""
    for cu in dwarf.iter_CUs():
        stack = [cu.get_top_DIE()]
        while stack:
            die = stack.pop()
            if (
                die.tag in AGGREGATES
                and _name(die) == struct_name
                and "DW_AT_declaration" not in die.attributes
            ):
                return die
            stack.extend(die.iter_children())
    return None


def _leaves(die: DIE, prefix: str, base: int):
    """(name, offset, type die) for every scalar leaf of an aggregate."""
    for child in die.iter_children():
        if child.tag != "DW_TAG_member" or "DW_AT_declaration" in child.attributes:
            continue  # a static data member has no storage inside the struct
        if "DW_AT_bit_size" in child.attributes:
            yield prefix + _name(child), None, None  # rejected in _field
            continue

        location = child.attributes.get("DW_AT_data_member_location")
        offset = base + (location.value if location else 0)
        name = _name(child)
        # An anonymous member contributes no name of its own to the path.
        path = f"{prefix}{name}" if name else prefix.rstrip(".")
        yield from _expand(path, offset, _type(child))


def _expand(path: str, offset: int, type_die: DIE):
    """Recurse into structs and arrays, yielding scalars as they are."""
    inner = _strip(type_die)
    if inner is not None and inner.tag in AGGREGATES:
        yield from _leaves(inner, f"{path}." if path else "", offset)
    elif inner is not None and inner.tag == "DW_TAG_array_type":
        element = _type(inner)
        stride = _size(element)
        dims = [_count(sub) for sub in inner.iter_children()]
        if stride is None or None in dims:
            yield path, offset, inner  # rejected in _field
            return
        yield from _array(path, offset, element, stride, dims)
    else:
        yield path, offset, type_die


def _array(path, offset, element, stride, dims):
    """Index a (possibly multidimensional) array, row major as c lays it out."""
    if not dims:
        yield from _expand(path, offset, element)
        return
    row = stride * math.prod(dims[1:])
    for i in range(dims[0]):
        yield from _array(f"{path}[{i}]", offset + i * row, element, stride, dims[1:])


def _field(name: str, offset: int | None, type_die: DIE | None) -> Field:
    if offset is None:
        raise ValueError("bitfields are not addressable")
    inner = _strip(type_die)
    if inner is None:
        raise ValueError("no type information")
    size = _size(inner)

    if inner.tag == "DW_TAG_base_type":
        encoding = inner.attributes["DW_AT_encoding"].value
        kind = KIND_BY_ENCODING.get(encoding)
    elif inner.tag == "DW_TAG_enumeration_type":
        underlying = _strip(_type(inner))
        encoding = underlying and underlying.attributes.get("DW_AT_encoding")
        kind = KIND_BY_ENCODING.get(encoding.value) if encoding else "uint"
    elif inner.tag == "DW_TAG_pointer_type":
        kind = "uint"
    else:
        raise ValueError(f"cannot address a {inner.tag.removeprefix('DW_TAG_')}")

    if kind is not None and size == 8:
        # No single m33 load or store covers 8 bytes, so the protocol stops
        # at 4 rather than hand out a value that could be torn mid update.
        raise ValueError("8 bytes is wider than one atomic access")
    if kind is None or size not in WIDTHS:
        raise ValueError(f"no {size} byte {_type_name(type_die)} on the wire")
    return Field(name, offset, size, kind, _type_name(type_die))


def _name(die: DIE) -> str:
    attr = die.attributes.get("DW_AT_name")
    return attr.value.decode() if attr else ""


def _type(die: DIE) -> DIE | None:
    return (
        die.get_DIE_from_attribute("DW_AT_type")
        if "DW_AT_type" in die.attributes
        else None
    )


def _strip(die: DIE | None) -> DIE | None:
    """Peel typedefs and cv qualifiers off until a type with a layout is left."""
    while die is not None and die.tag in QUALIFIERS:
        die = _type(die)
    return die


def _size(die: DIE | None) -> int | None:
    die = _strip(die)
    if die is None:
        return None
    if "DW_AT_byte_size" in die.attributes:
        return die.attributes["DW_AT_byte_size"].value
    if die.tag == "DW_TAG_array_type":
        dims = [_count(sub) for sub in die.iter_children()]
        stride = _size(_type(die))
        return None if stride is None or None in dims else stride * math.prod(dims)
    return None


def _count(subrange: DIE) -> int | None:
    if "DW_AT_count" in subrange.attributes:
        return subrange.attributes["DW_AT_count"].value
    if "DW_AT_upper_bound" in subrange.attributes:
        return subrange.attributes["DW_AT_upper_bound"].value + 1
    return None


def _type_name(die: DIE | None) -> str:
    """The spelling a human wrote, typedef and all (`uint32_t`, not `unsigned`)."""
    while die is not None and die.tag in ("DW_TAG_const_type", "DW_TAG_volatile_type"):
        die = _type(die)
    if die is None:
        return "void"
    if die.tag == "DW_TAG_pointer_type":
        return f"{_type_name(_type(die))} *"
    if die.tag == "DW_TAG_enumeration_type":
        return f"enum {_name(die) or '<anonymous>'}"
    return _name(die) or die.tag.removeprefix("DW_TAG_")
