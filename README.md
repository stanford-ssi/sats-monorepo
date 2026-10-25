# SSI Sats Monorepo

Flight software, ground tooling and sims for SSI's cubesat, in one Bazel
workspace. The firmware targets an RP2350 (pico 2).

## How to build an app

```bash
bazelisk build --config=pico //:blink
```

The uf2 and the elf both land in `bazel-bin/`, as `blink.uf2` and `blink`.

Note that `bazel-bin` is a symlink bazel repoints at whichever configuration
it built last, so running the host tests aims it at a tree with no firmware
in it. The ground tooling works around this by asking bazel where the pico
build went, but `bazel-bin/blink.uf2` in a flashing command is only valid
until the next host build.

## How to flash a pico

If the board is plugged in over usb and already running pico-sdk firmware,
picotool can reboot it into BOOTSEL itself:

``` bash
picotool load -f -x bazel-bin/blink.uf2
```

`-f` forces the reboot into BOOTSEL, `-x` starts the app once the load is
done. If the board is blank or wedged, hold the BOOTSEL button while
plugging it in and drop the `-f`:

``` bash
picotool load -x bazel-bin/blink.uf2
```

A board held in BOOTSEL also mounts as a mass storage device, so copying the
uf2 across works too:

``` bash
cp bazel-bin/blink.uf2 /media/$USER/RP2350/
```

To see what is currently flashed (`-f` reboots the board to read it):

``` bash
picotool info -a -f
```

## How to command a running board

The slate is the flight software's state struct. The `satcmd` python
package (in `ground/`) reads its field offsets and types out of the elf's
DWARF debug info, so they always match the binary you actually flashed, and
talks to the board over usb cdc.

### From a script

``` python
import satcmd

with satcmd.connect() as sat:          # port autodetected, elf is bazel-bin/blink
    sat.sleep_ms = 500                 # a write the board confirms
    assert sat.sleep_ms == 500         # a fresh read from the board
    assert sat.led_enabled
    print(sat.board_power.voltage)     # nested structs are attribute chains
    print(sat["board_power.current"])  # or dotted names
    print(sat.dump())                  # every field, by name
```

`connect(port, elf=..., struct="Slate", fake=False, timeout=0.3)`. With
`fake=True` an in process board serves a zeroed slate, which is enough to
try a script out with nothing plugged in. A misspelt field raises
`AttributeError` with a suggestion rather than silently doing nothing, a
value that does not fit the field raises `ValueError` before anything is
sent, and a refused or unanswered request raises `satcmd.BadAddress`,
`satcmd.BadWidth` or `satcmd.Timeout`.

float32 fields read back as the shortest decimal that is exactly that
float32, so `sat.temperature = 36.6` reads back as `36.6` rather than
`36.59999847`, and `==` does what you would expect.

### Interactively

``` bash
uv run satcmd                      # the browser, port autodetected
uv run satcmd --fake               # the same, against an in process board
uv run satcmd list                 # print the fields and exit
uv run satcmd read [FIELD...]      # print fields (all by default)
uv run satcmd write sleep_ms=500 board_power.voltage=3.3
uv run satcmd -v read sleep_ms     # log every frame on the wire
```

The browser draws in the last few lines of the terminal rather than taking
the screen over, so whatever you were looking at stays put and the last
frame is left behind when you quit, like any other command's output:

```
╭─ Slate ──────────────────────────────────── /dev/ttyACM0 ─╮
│   field                offset  type                 value │
│ › sleep_ms                  0  uint32_t               750 │
│   cycle_counter             4  uint32_t                 0 │
│   signed_scratch            8  int                      0 │
│   temperature              12  float                 36.6 │
│   board_power.voltage      16  float                  3.3 │
│   board_power.current      20  float                    0 │
│   led_enabled              24  bool                  true │
╰───────────────────────────────────────────────────────────╯
  sleep_ms <- 750
  w write · r refresh · a auto · j/k move · g/G ends · q quit
```

Every value shown is read back from the board rather than remembered
locally, so a refused write is visibly different from one that landed;
`BadAddress` and friends show up in the value column in red.

| key | |
|---|---|
| `j` / `k`, arrows | move |
| `g` / `G` | first / last field |
| `Ctrl-D` / `Ctrl-U` | half page |
| `w`, `i` or Enter | write to the selected field |
| Enter / `Esc` | commit / cancel a write |
| `r` | refresh all fields |
| `a` | toggle auto refresh |
| `q` or `:q` | quit |

Colour and box drawing are dropped automatically when stdout is not a
terminal, and `NO_COLOR` is honoured. Talking to the board needs
membership in the `dialout` group.

### The protocol

`proto/sats_command.proto` is the contract. There is one message, `SatMsg`:

| field | |
|---|---|
| `type` | 1 byte. `SatMsgType`: `READ`, `WRITE`, `READ_RESPONSE` or `WRITE_RESPONSE` |
| `width` | 1 byte. `Width`: `WIDTH_1_BYTE`, `_2_BYTES` or `_4_BYTES`; each value is its own byte count |
| `status` | 1 byte. Responses only: `OK`, `BAD_ADDRESS` or `BAD_WIDTH` |
| `offset` | `uint32`, byte offset into the answering node's memory |
| `value` | `uint32`, the raw bytes, little endian, in the low `width` bytes |

The three enums are stored as `uint8_t` on the c++ side
(`proto/sats_command.options`), and nanopb refuses a frame whose value does
not fit rather than truncating it. A value tops out at 32 bits because that
is the widest load or store the m33 makes in one instruction, so no read can
see a field half updated; 64 bit slate fields are listed as skipped.

It is symmetric: either end of a link can send requests and either can
answer them, so the same message works ground to flight or between two
microcontrollers. Responses echo `offset` and `width` so they can be
matched to their request, and carry what memory holds afterwards, so a
write is confirmed rather than assumed. Messages are nanopb encoded and
cobs framed, one zero byte per frame.

There are no types on the wire. The answering side copies bytes and
nothing else; what they mean (signed, float, bool) is known only to the
requester, which for the ground is the elf's debug info. On the c++ side
that is `SatLink` (`common/sat_link`, framing in both directions) and
`SlateServer` (`common/slate`, answers requests with a bounds and alignment
checked memcpy). Their python twins are `satcmd.Link` and
`satcmd.MemoryServer`.

## How to run the tests

``` bash
bazelisk test //...     # firmware and host c++
uv run pytest        # ground tooling
```

## Formatting

``` bash
bazelisk run //:format            # rewrite c++ with clang-format, python with ruff
bazelisk run //:format -- --check # verify only, what CI runs
uv run pre-commit install      # install the repository's git commit hooks
```

Only tracked files are formatted, so `git add` a new file before expecting
it to be touched. clang-format is pinned to an exact release in the uv dev
group (even 18.x patch releases disagree), so no system install is needed.

The commit hook formats the staged snapshot. If it changes anything, the
commit stops so you can review and stage the fixes before committing again.

## Run the CI checks locally

``` bash
bazelisk test //test:example_test --test_output=errors
bazelisk build --config=pico //:blink
```

## Other scripts

``` bash
uv run satcmd --elf path/to/elf --struct OtherStruct list   # any struct's layout
```
