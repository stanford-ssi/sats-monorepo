"""Commands: every variant has to survive a trip through the contract."""

import pytest

import cobs
from protocol import (
    Field,
    Unsupported,
    format_value,
    parse_value,
    read_cmd,
    width_of,
    write_cmd,
)
from sats_proto import SatCmd, SatResponse, Status, Width

U8 = Field("mode", 16, Width.WIDTH_U8)
U16 = Field("counter", 18, Width.WIDTH_U16)
U32 = Field("sleep_ms", 0, Width.WIDTH_U32)
F32 = Field("temperature", 4, Width.WIDTH_F32)


@pytest.mark.parametrize(
    "field, value, variant",
    [
        (U8, 0xAB, "write_u8"),
        (U16, 0xBEEF, "write_u16"),
        (U32, 0xDEADBEEF, "write_u32"),
        (F32, 36.5, "write_f32"),
    ],
)
def test_write_round_trip(field, value, variant):
    cmd = SatCmd.FromString(write_cmd(field, value).SerializeToString())
    assert cmd.WhichOneof("cmd") == variant
    assert getattr(cmd, variant).offset == field.offset
    assert getattr(cmd, variant).value == value


def test_read_round_trip():
    cmd = SatCmd.FromString(read_cmd(F32).SerializeToString())
    assert cmd.WhichOneof("cmd") == "read"
    assert (cmd.read.offset, cmd.read.width) == (4, Width.WIDTH_F32)


@pytest.mark.parametrize("field", [U8, U16, U32, F32])
def test_all_zero_command_still_makes_a_frame(field):
    """The whole message is zero valued, which proto3 loves to omit.

    An all default SatCmd used to serialise to nothing at all, and an empty
    frame is dropped by the receiver as a stray delimiter. The oneof tag
    keeps a byte on the wire now, but the property is worth pinning down.
    """
    cmd = write_cmd(Field(field.name, 0, field.width), 0)
    payload = cmd.SerializeToString()
    assert payload, "an all zero command must not serialise to nothing"
    assert cobs.frame(payload)
    assert SatCmd.FromString(payload).WhichOneof("cmd") is not None


def test_read_of_offset_zero_still_makes_a_frame():
    payload = read_cmd(Field("sleep_ms", 0, Width.WIDTH_U8)).SerializeToString()
    assert payload
    assert SatCmd.FromString(payload).read.width == Width.WIDTH_U8


@pytest.mark.parametrize(
    "field, value", [(U8, 256), (U16, 1 << 16), (U32, 1 << 32), (U8, -1)]
)
def test_out_of_range_writes_are_refused(field, value):
    with pytest.raises(ValueError):
        write_cmd(field, value)


@pytest.mark.parametrize(
    "text, expected", [("32", 32), ("0x20", 32), ("0b101", 5), (" 7 ", 7)]
)
def test_parse_integer_literals(text, expected):
    assert parse_value(text, U32) == expected


def test_parse_float():
    assert parse_value("36.5", F32) == 36.5
    with pytest.raises(ValueError):
        parse_value("nonsense", F32)


@pytest.mark.parametrize(
    "member, width",
    [
        ({"size": 1, "type": "uint8_t"}, Width.WIDTH_U8),
        ({"size": 2, "type": "uint16_t"}, Width.WIDTH_U16),
        ({"size": 4, "type": "uint32_t"}, Width.WIDTH_U32),
        ({"size": 4, "type": "float"}, Width.WIDTH_F32),
        ({"size": 1, "type": "bool"}, Width.WIDTH_U8),
    ],
)
def test_width_of_member(member, width):
    assert width_of(member) == width


@pytest.mark.parametrize(
    "member",
    [
        {"size": 8, "type": "double"},
        {"size": None, "type": "struct Thing"},
        {"size": 3, "type": "char [3]"},
    ],
)
def test_unaddressable_members_are_rejected(member):
    with pytest.raises(Unsupported):
        width_of(member)


def test_hand_encoded_default_response_is_readable():
    """CmdResponder spells out `status` when proto3 would emit nothing at all.

    That is not the canonical encoding of the message, so check the ground
    reads it back rather than assuming protobuf only ever sees its own output.
    """
    payload = bytes([1 << 3, 0])  # field 1 (status), varint, STATUS_UNSPECIFIED
    response = SatResponse.FromString(cobs.decode(cobs.frame(payload)))
    assert response.status == Status.STATUS_UNSPECIFIED
    assert format_value(response) == "UNSPECIFIED"


def test_format_surfaces_status():
    """A refusal has to read as a refusal, not as a missing value."""
    bad = SatResponse(status=Status.STATUS_BAD_OFFSET, offset=13)
    assert format_value(bad) == "BAD_OFFSET"
    assert format_value(SatResponse(status=Status.STATUS_BAD_COMMAND)) == "BAD_COMMAND"
    assert format_value(None) == "no reply"

    ok = SatResponse(status=Status.STATUS_OK, width=Width.WIDTH_F32, float_value=36.5)
    assert format_value(ok) == "36.5"
    assert format_value(SatResponse(status=Status.STATUS_OK, uint_value=250)) == "250"


BAD_INPUT = [
    ("nonsense", "u32", "'nonsense' is not a uint32"),
    ("", "u32", "no value given"),
    ("1.5", "u32", "'1.5' is not a uint32"),
    ("300", "u8", "300 does not fit in a uint8"),
    ("-1", "u32", "-1 does not fit in a uint32"),
    ("what", "f32", "'what' is not a float"),
]


@pytest.mark.parametrize("text,kind,expected", BAD_INPUT)
def test_bad_input_is_explained_in_terms_of_the_field(text, kind, expected):
    """A raw Python conversion error in the ui reads like a leaked stack
    trace; the message should name the field's type instead."""
    widths = {"u8": Width.WIDTH_U8, "u32": Width.WIDTH_U32, "f32": Width.WIDTH_F32}
    field = Field("thing", 0, widths[kind])
    with pytest.raises(ValueError) as err:
        parse_value(text, field)
    assert str(err.value) == expected


def test_good_input_still_parses():
    u32 = Field("thing", 0, Width.WIDTH_U32)
    assert parse_value("250", u32) == 250
    assert parse_value("0x20", u32) == 32
    assert parse_value("0b101", u32) == 5
    assert parse_value(" 7 ", u32) == 7
    assert parse_value("4294967295", u32) == 4294967295
    assert parse_value("36.5", Field("t", 0, Width.WIDTH_F32)) == 36.5
    assert parse_value("255", Field("m", 0, Width.WIDTH_U8)) == 255
