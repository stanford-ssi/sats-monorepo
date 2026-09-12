"""Field discovery out of DWARF, including nested structs.

The fixture is compiled here rather than read out of bazel-bin so the test
does not depend on the firmware having been built, or on the slate still
looking the way it does today.
"""

import shutil
import subprocess

import pytest

from parse_slate import get_struct_layout
from protocol import DW_ATE_FLOAT, fields_from_layout
from sats_proto import Width

SOURCE = """
#include <stdint.h>
struct PowerInfo { float voltage{}; float current{}; };
enum class Phase : uint8_t { BOOT, NOMINAL, SAFE };
enum Trim { TRIM_LEFT = -1, TRIM_CENTER = 0, TRIM_RIGHT = 1 };
struct Slate {
    uint32_t sleep_ms{250};
    float temperature{};
    PowerInfo board_power{};
    uint8_t mode{};
    uint16_t counter{};
    Phase phase{};
    Trim trim{};
};
Slate slate;
"""


@pytest.fixture(scope="module")
def elf(tmp_path_factory):
    if shutil.which("g++") is None:
        pytest.skip("no host compiler to build the dwarf fixture with")
    path = tmp_path_factory.mktemp("dwarf")
    (path / "slate.cpp").write_text(SOURCE)
    subprocess.run(
        ["g++", "-g", "-c", "slate.cpp", "-o", "slate.o"], cwd=path, check=True
    )
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
        "phase",
        "trim",
    ]


def test_flattened_offsets_are_absolute(elf):
    """board_power sits at 8, so its members are at 8 and 12, not 0 and 4."""
    layout = get_struct_layout(elf, "Slate")
    assert layout["board_power.voltage"]["offset"] == 8
    assert layout["board_power.current"]["offset"] == 12
    assert layout["counter"]["offset"] == 18  # after a byte of padding


def test_types_and_sizes_survive_flattening(elf):
    layout = get_struct_layout(elf, "Slate")
    assert layout["board_power.voltage"] == {
        "offset": 8,
        "size": 4,
        "type": "float",
        "encoding": DW_ATE_FLOAT,
    }
    assert layout["mode"]["size"] == 1


def test_unflattened_layout_still_available(elf):
    """The old view is what a caller that can only address words wants."""
    layout = get_struct_layout(elf, "Slate", flatten=False)
    assert layout["board_power"] == {
        "offset": 8,
        "size": 8,
        "type": "struct PowerInfo",
        "encoding": None,  # an aggregate has no base type encoding
    }


def test_every_flattened_member_is_addressable(elf):
    fields, skipped = fields_from_layout(get_struct_layout(elf, "Slate"))
    assert not skipped
    assert {f.name: f.type_name for f in fields}["board_power.current"] == "float"


def test_enum_constants_come_out_of_the_debug_info(elf):
    """The names are in the elf, so nothing has to be told about Phase."""
    layout = get_struct_layout(elf, "Slate")
    assert layout["phase"]["enumerators"] == (
        (0, "BOOT"),
        (1, "NOMINAL"),
        (2, "SAFE"),
    )
    assert layout["phase"]["size"] == 1
    assert layout["phase"]["type"] == "enum Phase"


def test_negative_enumerators_keep_their_sign(elf):
    layout = get_struct_layout(elf, "Slate")
    assert layout["trim"]["enumerators"] == (
        (-1, "TRIM_LEFT"),
        (0, "TRIM_CENTER"),
        (1, "TRIM_RIGHT"),
    )


def test_a_plain_member_carries_no_enumerators(elf):
    """The key is absent rather than empty, so ordinary records are unchanged."""
    layout = get_struct_layout(elf, "Slate")
    assert "enumerators" not in layout["mode"]
    assert "enumerators" not in layout["board_power.voltage"]


def test_enums_are_addressable_at_their_underlying_width(elf):
    """Phase is a byte and Trim is a signed word; neither is a special case."""
    fields, skipped = fields_from_layout(get_struct_layout(elf, "Slate"))
    assert not skipped
    by_name = {f.name: f for f in fields}

    assert by_name["phase"].width == Width.WIDTH_U8
    assert by_name["trim"].width == Width.WIDTH_I32  # a negative enumerator

    assert by_name["phase"].is_enum
    assert by_name["phase"].type_name == "enum Phase"
    assert by_name["phase"].enum_name(2) == "SAFE"
    assert by_name["trim"].enum_value("trim_left") == -1
    assert not by_name["mode"].is_enum


def test_missing_struct_is_an_error(elf):
    with pytest.raises(ValueError):
        get_struct_layout(elf, "NotAStruct")
