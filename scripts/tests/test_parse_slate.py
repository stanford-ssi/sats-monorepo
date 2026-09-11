"""Field discovery out of DWARF, including nested structs.

The fixture is compiled here rather than read out of bazel-bin so the test
does not depend on the firmware having been built, or on the slate still
looking the way it does today.
"""

import shutil
import subprocess

import pytest

from parse_slate import get_struct_layout
from protocol import fields_from_layout

SOURCE = """
#include <stdint.h>
struct PowerInfo { float voltage{}; float current{}; };
struct Slate {
    uint32_t sleep_ms{250};
    float temperature{};
    PowerInfo board_power{};
    uint8_t mode{};
    uint16_t counter{};
};
Slate slate;
"""


@pytest.fixture(scope="module")
def elf(tmp_path_factory):
    if shutil.which("g++") is None:
        pytest.skip("no host compiler to build the dwarf fixture with")
    path = tmp_path_factory.mktemp("dwarf")
    (path / "slate.cpp").write_text(SOURCE)
    subprocess.run(["g++", "-g", "-c", "slate.cpp", "-o", "slate.o"], cwd=path, check=True)
    return str(path / "slate.o")


def test_nested_members_are_flattened(elf):
    layout = get_struct_layout(elf, "Slate")
    assert list(layout) == [
        "sleep_ms",
        "temperature",
        "board_power.voltage",
        "board_power.current",
        "mode",
        "counter",
    ]


def test_flattened_offsets_are_absolute(elf):
    """board_power sits at 8, so its members are at 8 and 12, not 0 and 4."""
    layout = get_struct_layout(elf, "Slate")
    assert layout["board_power.voltage"]["offset"] == 8
    assert layout["board_power.current"]["offset"] == 12
    assert layout["counter"]["offset"] == 18  # after a byte of padding


def test_types_and_sizes_survive_flattening(elf):
    layout = get_struct_layout(elf, "Slate")
    assert layout["board_power.voltage"] == {"offset": 8, "size": 4, "type": "float"}
    assert layout["mode"]["size"] == 1


def test_unflattened_layout_still_available(elf):
    """The old view is what a caller that can only address words wants."""
    layout = get_struct_layout(elf, "Slate", flatten=False)
    assert layout["board_power"] == {"offset": 8, "size": 8, "type": "struct PowerInfo"}


def test_every_flattened_member_is_addressable(elf):
    fields, skipped = fields_from_layout(get_struct_layout(elf, "Slate"))
    assert not skipped
    assert {f.name: f.type_name for f in fields}["board_power.current"] == "float"


def test_missing_struct_is_an_error(elf):
    with pytest.raises(ValueError):
        get_struct_layout(elf, "NotAStruct")
