#!/usr/bin/env python3
"""
sats_proto.py - python bindings for the frozen proto/sats_command.proto.

The bindings are compiled from the .proto itself the first time this module
is imported, rather than being committed alongside it. The contract is shared
with the firmware, so the one failure mode worth engineering out is the
ground software silently believing an older version of it: generated code
that is derived from the file on disk cannot drift from the file on disk.

protoc output is cached in a temp dir keyed by a hash of the .proto's
contents, so the compile only actually runs when the contract changes.

Usage:
    from sats_proto import SatCmd, SatResponse, Width, Status
"""

import hashlib
import importlib.util
import sys
import tempfile
from pathlib import Path

PROTO_PATH = Path(__file__).resolve().parent.parent / "proto" / "sats_command.proto"


def _compile_proto(proto: Path) -> Path:
    """protoc the contract into a cache dir and return the generated module."""
    digest = hashlib.sha256(proto.read_bytes()).hexdigest()[:16]
    out_dir = Path(tempfile.gettempdir()) / f"sats_proto_{digest}"
    generated = out_dir / f"{proto.stem}_pb2.py"
    if generated.exists():
        return generated

    from grpc_tools import protoc  # slow import, skipped on a cache hit

    out_dir.mkdir(parents=True, exist_ok=True)
    code = protoc.main(
        [
            "protoc",
            f"--proto_path={proto.parent}",
            f"--python_out={out_dir}",
            str(proto),
        ]
    )
    if code != 0:
        raise RuntimeError(f"protoc failed on {proto} (exit {code})")
    return generated


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # protobuf's generated code expects to be importable
    spec.loader.exec_module(module)
    return module


if not PROTO_PATH.exists():
    raise RuntimeError(f"contract not found at {PROTO_PATH}")

_pb2 = _load(_compile_proto(PROTO_PATH), "sats_command_pb2")

SatCmd = _pb2.SatCmd
SatResponse = _pb2.SatResponse
WriteU8 = _pb2.WriteU8
WriteU16 = _pb2.WriteU16
WriteU32 = _pb2.WriteU32
WriteF32 = _pb2.WriteF32
ReadField = _pb2.ReadField
Width = _pb2.Width
Status = _pb2.Status
