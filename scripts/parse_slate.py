#!/usr/bin/env python3
"""
parse_slate.py - dump field offsets/sizes/types for a struct from an ELF's
DWARF debug info.

Usage:
    uv run scripts/parse_slate.py <path-to-elf> <StructName> [--flat] [--json]

Notes:
    - The ELF must be compiled with debug info (-g).
    - If multiple structs share the name (e.g. compiled in from different
      translation units), all matches are printed.
"""

import argparse
import json
import sys

from elftools.dwarf.die import DIE
from elftools.elf.elffile import ELFFile


def type_name(die: DIE) -> str:
    """Best-effort human-readable type name for a DIE, resolving qualifiers/pointers."""
    if die is None:
        return "void"

    tag = die.tag
    if tag == "DW_TAG_base_type":
        return die.attributes["DW_AT_name"].value.decode()

    if tag in ("DW_TAG_structure_type", "DW_TAG_union_type", "DW_TAG_enumeration_type"):
        name = die.attributes.get("DW_AT_name")
        prefix = {
            "DW_TAG_structure_type": "struct",
            "DW_TAG_union_type": "union",
            "DW_TAG_enumeration_type": "enum",
        }[tag]
        return f"{prefix} {name.value.decode()}" if name else f"{prefix} <anonymous>"

    if tag == "DW_TAG_pointer_type":
        target = (
            die.get_DIE_from_attribute("DW_AT_type")
            if "DW_AT_type" in die.attributes
            else None
        )
        return f"{type_name(target)} *"

    if tag == "DW_TAG_const_type":
        target = (
            die.get_DIE_from_attribute("DW_AT_type")
            if "DW_AT_type" in die.attributes
            else None
        )
        return f"const {type_name(target)}"

    if tag == "DW_TAG_volatile_type":
        target = (
            die.get_DIE_from_attribute("DW_AT_type")
            if "DW_AT_type" in die.attributes
            else None
        )
        return f"volatile {type_name(target)}"

    if tag == "DW_TAG_typedef":
        name = die.attributes.get("DW_AT_name")
        return name.value.decode() if name else "typedef"

    if tag == "DW_TAG_array_type":
        target = (
            die.get_DIE_from_attribute("DW_AT_type")
            if "DW_AT_type" in die.attributes
            else None
        )
        count = None
        for child in die.iter_children():
            if (
                child.tag == "DW_TAG_subrange_type"
                and "DW_AT_upper_bound" in child.attributes
            ):
                count = child.attributes["DW_AT_upper_bound"].value + 1
        suffix = f"[{count}]" if count is not None else "[]"
        return f"{type_name(target)} {suffix}"

    return tag


def die_byte_size(die: DIE):
    if die is None:
        return None
    if "DW_AT_byte_size" in die.attributes:
        return die.attributes["DW_AT_byte_size"].value
    if die.tag in ("DW_TAG_pointer_type",):
        return 8  # assume 64-bit target unless overridden
    if die.tag in ("DW_TAG_const_type", "DW_TAG_volatile_type", "DW_TAG_typedef"):
        target = (
            die.get_DIE_from_attribute("DW_AT_type")
            if "DW_AT_type" in die.attributes
            else None
        )
        return die_byte_size(target)
    if die.tag == "DW_TAG_array_type":
        target = (
            die.get_DIE_from_attribute("DW_AT_type")
            if "DW_AT_type" in die.attributes
            else None
        )
        elem_size = die_byte_size(target)
        count = None
        for child in die.iter_children():
            if (
                child.tag == "DW_TAG_subrange_type"
                and "DW_AT_upper_bound" in child.attributes
            ):
                count = child.attributes["DW_AT_upper_bound"].value + 1
        if elem_size is not None and count is not None:
            return elem_size * count
        return None
    return None


def find_structs(dwarf_info, struct_name):
    matches = []
    for CU in dwarf_info.iter_CUs():
        top = CU.get_top_DIE()
        for die in top.iter_children():
            _walk(die, struct_name, matches)
    return matches


def _walk(die, struct_name, matches):
    if die.tag == "DW_TAG_structure_type":
        name = die.attributes.get("DW_AT_name")
        if name and name.value.decode() == struct_name:
            matches.append(die)
    for child in die.iter_children():
        _walk(child, struct_name, matches)


AGGREGATE_TAGS = ("DW_TAG_structure_type", "DW_TAG_class_type", "DW_TAG_union_type")


def target_type(die: DIE):
    """The DIE a type or member points at, if it points at one."""
    return (
        die.get_DIE_from_attribute("DW_AT_type")
        if "DW_AT_type" in die.attributes
        else None
    )


def strip_qualifiers(die: DIE):
    """Peel typedefs and cv qualifiers off until a type with a layout is left."""
    while die is not None and die.tag in (
        "DW_TAG_typedef",
        "DW_TAG_const_type",
        "DW_TAG_volatile_type",
    ):
        die = target_type(die)
    return die


def struct_members(
    die: DIE, flatten: bool = False, prefix: str = "", base: int = 0
) -> list:
    """Field records for a struct's members, with offsets relative to `base`.

    With `flatten`, a member that is itself a struct is replaced by its own
    members under a dotted name, so `board_power.voltage` is reported at the
    absolute offset the firmware would use for it. Without it the nested
    struct stays one opaque member, which is all a caller that can only
    address whole words can use anyway.
    """
    fields = []
    for child in die.iter_children():
        if child.tag != "DW_TAG_member" or "DW_AT_declaration" in child.attributes:
            continue  # a static data member has no storage inside the struct

        name = child.attributes.get("DW_AT_name")
        name = name.value.decode() if name else ""
        location = child.attributes.get("DW_AT_data_member_location")
        offset = base + (location.value if location else 0)
        ftype_die = target_type(child)

        inner = strip_qualifiers(ftype_die)
        if flatten and inner is not None and inner.tag in AGGREGATE_TAGS:
            # An anonymous member contributes no name of its own to the path.
            nested_prefix = f"{prefix}{name}." if name else prefix
            nested = struct_members(inner, flatten, nested_prefix, offset)
            if nested:
                fields += nested
                continue

        fields.append(
            {
                "name": prefix + name,
                "offset": offset,
                "size": die_byte_size(ftype_die),
                "type": type_name(ftype_die),
            }
        )

    return fields


def dump_struct(die: DIE, flatten: bool = False):
    total_size = die.attributes.get("DW_AT_byte_size")
    total_size = total_size.value if total_size else None
    return {"size": total_size, "fields": struct_members(die, flatten)}


def get_struct_layout(elf_path: str, struct_name: str, flatten: bool = True) -> dict:
    """Returns {field_name: {'offset': int, 'size': int, 'type': str}}

    Flattens nested structs by default: every leaf is separately addressable
    by the command set, so `board_power.voltage` is more useful to a caller
    than an eight byte `board_power` it cannot do anything with.
    """
    with open(elf_path, "rb") as f:
        elf = ELFFile(f)
        dwarf_info = elf.get_dwarf_info()
        matches = find_structs(dwarf_info, struct_name)

        if not matches:
            raise ValueError(f"struct '{struct_name}' not found")

        result = dump_struct(matches[0], flatten)  # first match

    return {
        f["name"]: {"offset": f["offset"], "size": f["size"], "type": f["type"]}
        for f in result["fields"]
    }


def main():
    parser = argparse.ArgumentParser(
        description="Dump struct layout from ELF DWARF info"
    )
    parser.add_argument("elf_path")
    parser.add_argument("struct_name")
    parser.add_argument(
        "--json", action="store_true", help="output as JSON instead of a table"
    )
    parser.add_argument(
        "--flat", action="store_true", help="expand nested structs into dotted members"
    )
    args = parser.parse_args()

    with open(args.elf_path, "rb") as f:
        elf = ELFFile(f)
        if not elf.has_dwarf_info():
            print(
                f"error: {args.elf_path} has no DWARF debug info (compile with -g)",
                file=sys.stderr,
            )
            sys.exit(1)

        dwarf_info = elf.get_dwarf_info()
        matches = find_structs(dwarf_info, args.struct_name)

        if not matches:
            print(f"error: struct '{args.struct_name}' not found", file=sys.stderr)
            sys.exit(1)

        results = [dump_struct(die, args.flat) for die in matches]

    if args.json:
        print(json.dumps(results, indent=2))
        return

    for i, result in enumerate(results):
        if len(results) > 1:
            print(f"=== match {i + 1} ===")
        size = result["size"]
        print(f"struct {args.struct_name} {{  /* size: {size} */")
        prev_end = 0
        for field in result["fields"]:
            if field["offset"] > prev_end:
                hole = field["offset"] - prev_end
                print(f"    /* XXX {hole} byte hole */")
            fsize_str = field["size"] if field["size"] is not None else "?"
            print(
                f"    {field['type']:<20} {field['name']:<20}"
                f" /* offset {field['offset']:>4}  size {fsize_str} */"
            )
            if field["size"] is not None:
                prev_end = field["offset"] + field["size"]
        if size is not None and prev_end < size:
            print(f"    /* XXX {size - prev_end} byte tail padding */")
        print("};")


if __name__ == "__main__":
    main()
