"""Commands: every variant has to survive a trip through the contract."""

import pytest

import cobs
from protocol import (
    DW_ATE_BOOLEAN,
    DW_ATE_FLOAT,
    DW_ATE_SIGNED,
    DW_ATE_SIGNED_CHAR,
    DW_ATE_UNSIGNED,
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
        # A bool is a byte, but it is not a uint8: the debug info's type
        # name is what tells them apart.
        ({"size": 1, "type": "bool"}, Width.WIDTH_BOOL),
        ({"size": 1, "type": "_Bool"}, Width.WIDTH_BOOL),
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


BOOL_FIELD = Field("enabled", 4, Width.WIDTH_BOOL)

BOOL_INPUT = [
    ("true", True),
    ("false", False),
    ("True", True),
    ("FALSE", False),  # case is not the user's problem
    ("1", True),
    ("0", False),
    ("on", True),
    ("off", False),
    ("yes", True),
    ("no", False),
    ("t", True),
    ("f", False),
    (" true ", True),  # stray whitespace
]


@pytest.mark.parametrize("text,expected", BOOL_INPUT)
def test_bool_input(text, expected):
    assert parse_value(text, BOOL_FIELD) is expected


@pytest.mark.parametrize("text", ["2", "-1", "maybe", "", "truthy"])
def test_bad_bool_input_is_refused(text):
    """`2` is refused on purpose: a slate bool that is neither true nor
    false is a bug worth seeing, not something to coerce."""
    with pytest.raises(ValueError):
        parse_value(text, BOOL_FIELD)


def test_a_bool_field_is_one_byte_and_named_bool():
    assert BOOL_FIELD.size == 1
    assert BOOL_FIELD.type_name == "bool"
    assert BOOL_FIELD.is_bool and not BOOL_FIELD.is_float


def test_bool_write_uses_the_bool_variant():
    cmd = write_cmd(BOOL_FIELD, True)
    assert cmd.WhichOneof("cmd") == "write_bool"
    assert cmd.write_bool.offset == 4
    assert cmd.write_bool.value is True


def test_a_false_bool_write_is_still_a_non_empty_frame():
    """An all-default message encodes to zero bytes and the firmware drops
    the resulting empty frame, so `enabled = false` at offset 0 has to
    survive the oneof wrapper."""
    cmd = write_cmd(Field("enabled", 0, Width.WIDTH_BOOL), False)
    assert len(cmd.SerializeToString()) > 0


def test_bool_formats_as_a_word_not_a_number():
    for value, expected in ((True, "true"), (False, "false")):
        rsp = SatResponse(
            status=Status.STATUS_OK,
            offset=4,
            width=Width.WIDTH_BOOL,
            bool_value=value,
        )
        assert format_value(rsp) == expected


I8 = Field("trim", 0, Width.WIDTH_I8)
I16 = Field("offset_hz", 0, Width.WIDTH_I16)
I32 = Field("drift", 0, Width.WIDTH_I32)


def test_signed_fields_report_signed_limits():
    assert I8.limits == (-128, 127)
    assert I16.limits == (-32768, 32767)
    assert I32.limits == (-2147483648, 2147483647)
    assert U32.limits == (0, 4294967295)
    assert I32.is_signed and not U32.is_signed


@pytest.mark.parametrize(
    "text,expected",
    [("-1", -1), ("0", 0), ("127", 127), ("-128", -128), ("-0x10", -16)],
)
def test_signed_input(text, expected):
    assert parse_value(text, I8) == expected


@pytest.mark.parametrize("text", ["128", "-129", "1000"])
def test_signed_input_out_of_range_is_refused(text):
    with pytest.raises(ValueError, match="does not fit"):
        parse_value(text, I8)


def test_negative_input_is_still_refused_for_unsigned():
    with pytest.raises(ValueError, match="does not fit"):
        parse_value("-1", U32)


def test_signed_writes_use_the_signed_variants():
    for field, variant in ((I8, "write_i8"), (I16, "write_i16"), (I32, "write_i32")):
        cmd = write_cmd(field, -5)
        assert cmd.WhichOneof("cmd") == variant
        assert getattr(cmd, variant).value == -5


def test_a_negative_value_costs_few_bytes_on_the_wire():
    """sint32 zigzags, so -1 is cheap. A plain int32 would sign extend it
    into ten bytes of varint, which matters on a radio link."""
    assert len(write_cmd(I32, -1).SerializeToString()) <= 6


SIGNED_ENCODINGS = [
    ({"size": 1, "type": "int8_t", "encoding": DW_ATE_SIGNED_CHAR}, Width.WIDTH_I8),
    ({"size": 2, "type": "int16_t", "encoding": DW_ATE_SIGNED}, Width.WIDTH_I16),
    ({"size": 4, "type": "int32_t", "encoding": DW_ATE_SIGNED}, Width.WIDTH_I32),
    ({"size": 4, "type": "unsigned int", "encoding": DW_ATE_UNSIGNED}, Width.WIDTH_U32),
    ({"size": 1, "type": "bool", "encoding": DW_ATE_BOOLEAN}, Width.WIDTH_BOOL),
    ({"size": 4, "type": "float", "encoding": DW_ATE_FLOAT}, Width.WIDTH_F32),
]


@pytest.mark.parametrize("member,width", SIGNED_ENCODINGS)
def test_encoding_decides_the_width(member, width):
    """Size cannot tell a uint8 from an int8 from a bool, so the encoding
    is what the choice actually rests on."""
    assert width_of(member) == width


def test_encoding_beats_a_misleading_type_name():
    member = {"size": 4, "type": "uint32_t", "encoding": DW_ATE_SIGNED}
    assert width_of(member) == Width.WIDTH_I32


def test_a_layout_without_an_encoding_falls_back_to_the_name():
    assert width_of({"size": 4, "type": "int32_t"}) == Width.WIDTH_I32
    assert width_of({"size": 1, "type": "bool"}) == Width.WIDTH_BOOL
