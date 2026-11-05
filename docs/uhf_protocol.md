# UHF Protocol

How the satellite and ground station talk over the 433 MHz (UHF) link: what is
in a packet, and how each side handles it.

Schemas live in [`proto/`](../proto):

| File | Contents |
|---|---|
| [`uhf_packet.proto`](../proto/uhf_packet.proto) | Envelope: `Packet`, `Header`, `Request`, `Response`, `ResultCode`, `NodeAddress` |
| [`sats_command.proto`](../proto/sats_command.proto) | Memory access: `SatCmd` / `SatResponse` (unchanged) |
| [`uhf_file.proto`](../proto/uhf_file.proto) | Files: GET, PUT, HEAD, LIST, DELETE on paths |
| [`uhf_command.proto`](../proto/uhf_command.proto) | Commands: Reboot, TransmitOff, TransmitOn |
| [`uhf_beacon.proto`](../proto/uhf_beacon.proto) | Beacon |

`uhf_packet.proto` imports the others. It is the router: the one place that
lists every protocol. The other files do not depend on each other.

## 1. Goals

1. **Minimal, and add-only.** The protocol holds only what we are confident will
   last. Over time we add fields and `oneof` variants; nothing is removed,
   renumbered or given a new meaning. Anything we are unsure about is left out
   rather than guessed at.
2. **Generic over specific.** The protos describe *how* to reach things
   (memory offsets, file paths), not *what* the things are. Meaning lives with
   the firmware build, so firmware can change without the protocol changing.
3. **Safe to retry.** Radio packets are lost and duplicated. Every operation
   except commands can be resent blindly.
4. **Symmetric.** One `Packet` type and one layout in both directions.

## 2. On-air layout

```
byte 0    to      NodeAddress   ┐
byte 1    from    NodeAddress   │ RadioHead header, raw
byte 2    id      sequence      │
byte 3    flags                 ┘
byte 4+   Packet  protobuf
last 16   HMAC-SHA256           over every byte before it, truncated to 16 bytes
```

RadioHead's RF95 driver allows 251 bytes after its 4-byte header, shared by the
protobuf and the HMAC. The HMAC is raw so a packet is authenticated before any
of it is decoded. Every packet carries it, in both directions.

## 3. Who does what

Five mechanisms, each with a clear boundary. The test that sorts most cases:
**would it be bad if this arrived twice, or at the wrong moment?**

| Mechanism | Why we need it | Started by | Safe to repeat | Size |
|---|---|---|---|---|
| **Memory** (`SatCmd`) | Most flexible, and the standard approach: any slate value (parameters, flags, current state) can be read or set without new protocol | Ground | Yes | ≤ 1 packet |
| **Files** | Data bigger than a packet or kept in flash (logs, config, later firmware) needs reliable multi-packet transfer | Ground | Yes | any |
| **Commands** | Actions with side effects that are not safe to repeat, and recovery that must work even when memory access does not | Ground | No | 1 packet |
| **Ping** | The cheapest "are you there?", with no dependency on the build or the slate | Ground | Yes | tiny |
| **Beacon** | The only thing that reaches the ground unprompted, so it works when the uplink is down or no session is running | Satellite, periodically | n/a | 1 packet |

### Commands

Anything that can be a slate write goes through memory. Commands are kept to a
minimal set: actions that are not safe to repeat, or critical enough that they
must work even when memory access does not (wrong build, corrupted slate).

- `reboot`: the universal recovery action.
- `transmit_off`: licensing requires that the satellite stop transmitting on
  command if a regulator orders it, e.g. FCC 47 CFR 97.207(b) for amateur space
  stations ("must be capable of effecting a cessation of transmissions by
  telecommand whenever such cessation is ordered by the FCC").
- `transmit_on`: ends a `transmit_off` early, since the satellite keeps listening.

### Beacon

The beacon is its own `Packet` variant, not a file `put` from the satellite to
the ground, because:

- A `put` is a request: it takes a request id and expects a reply. Nobody
  answers a beacon, and the satellite must never wait on one.
- A `put` carries a path and offset that mean nothing for a beacon, costing
  bytes every few seconds for the whole mission.
- File contents are opaque bytes. A beacon's fields are typed, so anyone with
  the proto can decode it, with no ELF and no agreed file format.

## 4. Files

Stateless methods on paths, in the style of HTTP. The satellite keeps no
session, so a reboot mid-transfer loses nothing: the ground resumes from where
it got to. File contents are opaque bytes to this protocol, so formats (logs,
for example) are defined separately and later.

| Method | Meaning | Answer |
|---|---|---|
| `get {offset, length}` | Read a byte range (`length` 0 = to end) | `FileData` packets |
| `put {offset, data}` | Write at an offset; offset 0 creates a missing file; never truncates | result code |
| `head` | Size, CRC and type of one path, like `stat` | `FileInfo` |
| `list` | `ls` on a directory, or on a single file | `FileListing` packets |
| `delete` | Remove the file | result code |

## 5. Security

Every packet, in both directions, ends in an HMAC-SHA256 truncated to 16 bytes,
in accordance with RFC 2104 and IPsec's HMAC-SHA-256-128 (RFC 4868).

## 6. Handling

### Receiving a packet

Satellite and ground process every packet in this order. A packet that fails
steps 1 to 3 is dropped with no reply, since replying would let anyone make the
satellite transmit; the satellite counts it in `Beacon.requests_rejected`.

1. **Authenticate.** Verify the HMAC with the key for the packet's direction,
   using a constant-time comparison (not `memcmp`, which leaks timing).
2. **Check the sender.** Drop a packet whose `from` byte names the receiver.
3. **Check for replays** (see below), then record the request id as accepted.
4. **Decode.** A packet that does not decode gets `RESULT_CODE_BAD_REQUEST`.
5. **Check the build.** Memory access needs `Header.build_id` to match, or gets
   `RESULT_CODE_WRONG_BUILD`. Ping, files and commands skip this check.
6. **Dispatch.** No operation set, or one this firmware does not know, gets
   `RESULT_CODE_UNSUPPORTED`. This is what makes every later addition safe.

### Requests and responses

- Every response carries the id of the request it answers. Answers longer than
  a packet (`get`, `list`) arrive as several packets, with `last` set on the
  final one.
- After a timeout, the requester resends with a **new** id: the old one has
  been used, so a resend under it would be rejected as a replay. Everything
  except commands is safe to resend. Before resending a command, check
  `Beacon.last_request_id` to see whether the first attempt was accepted.
- Commands reply before taking effect.

### Keys

Each direction has its own key, derived from one master secret, so a packet
signed for one direction can never be reflected back in the other:

```
K_up   = HMAC-SHA256(K, "uplink")
K_down = HMAC-SHA256(K, "downlink")
```

The master key never goes in git. On the satellite it lives where a filesystem
reformat cannot erase it; losing it means losing the satellite.

### Replay protection

A request is accepted only if `Header.boot_count` equals the satellite's
current boot count and `Request.id` is greater than the last id accepted from
that sender in this boot. A recorded packet fails one or the other. Gaps from
lost packets are fine, and the id sequence restarts with each boot count.

The ground also rejects downlinks whose `boot_count` is lower than the latest
it has seen, and beacons whose `onboard_clock_ms` or `time_since_boot_s` goes backwards within a boot.

If the satellite goes quiet (after `transmit_off`, or a transmitter fault), the
ground can still command it with the last boot count it knows, trying the next
few if the satellite may have rebooted. Wrong guesses are dropped harmlessly.

### Requests from the satellite

The protocol is symmetric, so the satellite may send requests too, for example
a `put` that pushes a log to the ground. The same rules apply in reverse: the
satellite numbers its requests in its own increasing sequence per boot, and the
ground answers with a `Response`. The beacon is the only message that expects
no answer.

### File Transfer Protocol logic flow

| Task | Steps |
|---|---|
| Download | `list` the directory, `get` the file, re-`get` any gaps, then optionally `head` and compare the CRC |
| Upload | `delete` if replacing, `put` the chunks, then `head` and compare size and CRC |

## 7. Response to the FTP/VFS design proposal

This protocol builds on the FTP/VFS design proposal (TM-000001): a symmetric
protocol, and file transfer for logs. It departs from the proposal in two
places.

### Stateless paths instead of open and close

The proposal follows the Unix interface: `Open` returns a file descriptor,
`Read` and `Write` use it, `Close` releases it, and a timeout closes
descriptors that are abandoned. Here every request carries its path and the
satellite keeps no state between requests.

On this link descriptors leak: a lost `Close`, a pass that ends mid-transfer or
a reboot all strand open descriptors, which is why the proposal needs a timeout.
Stateless requests remove that whole class of problem. There is no descriptor
table, no timeout, nothing lost on reboot, and every request can be resent
safely. The cost is the path on every request, about a dozen bytes. Handles can
still be added later as an option if uploads make paths too expensive.

### Commands as separate messages, not file writes

The proposal suggests commands could be writes to a file, such as a ring
buffer, which would remove the separate command protocol. A fixed path like
`/sys/reboot` would be just as independent of the build as our fixed commands.

We keep commands separate because file methods are meant to be safe to repeat:
a `put` resent after a lost reply must leave the same result. A write that
reboots the satellite or silences its transmitter does not. A dedicated
`Command` also gives arguments a type the schema checks, and keeps the few
dangerous actions in one visible place instead of among paths. The cost is one
more message type, kept to a minimal set.

## 8. Future additions

Each can be added without editing what exists.

- Log format: COBS-framed `LogEntry` protobuf records, so a corrupted record
  does not lose the rest of the file.
- Read-only slate fields.
- Rename (`move`), so an upload can be checked before it replaces a file.
- Time-tagged commands ("do X at time T").
- Custom commands defined by a firmware build (an opcode plus arguments from
  the build's command dictionary), once one has a concrete need.
- Adding a limit to GET size over FTP.

## 9. Open questions

- **Chunk limit per GET.** A starting value, and whether it is in packets or
  bytes.
- **TransmitOff policy.** SAMWISE required the command three times in a row and
  limited silence to three months. Whether we keep either rule, now that
  uplinks are authenticated, is a firmware decision to record here.
- **nanopb sizes.** `string`, `bytes` and `repeated` fields need maximum sizes
  in `.options` files for static allocation on the satellite.
