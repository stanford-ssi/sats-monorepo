# Protobuf Definitions

All protobufs used to communicate on the satellite need to be referenced
between different projects and so belong in this folder in common

Install protoc the compiler for protobufs. [https://github.com/protocolbuffers/protobuf/blob/main/src/README.md]

The UHF link protocol (`uhf_*.proto`) is described in
[docs/uhf_protocol.md](../docs/uhf_protocol.md). When editing, fields and `oneof` variants
may be added, never removed, renumbered or given a new meaning.
