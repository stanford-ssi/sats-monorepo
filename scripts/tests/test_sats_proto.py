"""The bindings are generated, so this guards the assumptions around them.

Nothing here re-tests protobuf; it checks that the names and numbers this
tooling hardcodes are still the ones the frozen contract defines, and fails
loudly at test time rather than mysteriously at runtime if the .proto moves.
"""

from sats_proto import PROTO_PATH, SatCmd, SatResponse, Status, Width


def test_generated_from_the_repo_contract():
    assert PROTO_PATH.exists()
    assert PROTO_PATH.read_text().startswith('syntax = "proto3"')


def test_command_variants():
    oneof = SatCmd.DESCRIPTOR.oneofs_by_name["cmd"]
    assert [f.name for f in oneof.fields] == [
        "write_u8",
        "write_u16",
        "write_u32",
        "write_f32",
        "read",
        "write_bool",
        "write_i8",
        "write_i16",
        "write_i32",
    ]


def test_response_variants():
    assert {f.name for f in SatResponse.DESCRIPTOR.oneofs_by_name["value"].fields} == {
        "uint_value",
        "float_value",
        "bool_value",
        "int_value",
    }


def test_enum_values():
    assert Width.WIDTH_UNSPECIFIED == 0  # the default, and never addressable
    # Pinned numbers: these go on the wire, so renumbering one silently
    # would make old ground software talk nonsense to new firmware.
    assert [
        Width.WIDTH_U8,
        Width.WIDTH_U16,
        Width.WIDTH_U32,
        Width.WIDTH_F32,
        Width.WIDTH_BOOL,
        Width.WIDTH_I8,
        Width.WIDTH_I16,
        Width.WIDTH_I32,
    ] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert Status.STATUS_OK == 1
    assert Status.Name(Status.STATUS_BAD_OFFSET) == "STATUS_BAD_OFFSET"
