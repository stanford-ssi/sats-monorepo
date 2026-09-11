# SSI Sats Monorepo

Flight software, ground tooling and sims for SSI's cubesat, in one Bazel
workspace. The firmware targets an RP2350 (pico 2).

## How to build an app

```bash
bazel build --config=pico //:blink
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

The slate is the flight software's state struct. `satui.py` reads its field
offsets out of the elf's DWARF debug info, so the offsets always match the
binary you actually flashed, and talks to the board over usb cdc.

``` bash
uv run scripts/satui.py            # the ui, port autodetected
uv run scripts/satui.py --list     # print the fields and exit
uv run scripts/satui.py --fake     # run against an in process fake board
uv run scripts/satui.py --set sleep_ms=500 --set board_power.voltage=3.3
```

The ui draws in the last few lines of the terminal rather than taking the
screen over, so whatever you were looking at stays put and the last frame
is left behind when you quit, like any other command's output:

```
╭─ Slate ──────────────────────────────────── /dev/ttyACM0 ─╮
│   field                offset  type                 value │
│ › sleep_ms                  0  uint32                 250 │
│   temperature               4  float                 36.5 │
│   board_power.voltage       8  float                  3.3 │
│   board_power.current      12  float                 0.75 │
╰───────────────────────────────────────────────────────────╯
  sleep_ms <- 250
  w write · r refresh · a auto · j/k move · g/G ends · q quit
```

Every value shown is read back from the board rather than remembered
locally, so a refused write is visibly different from one that landed;
`BAD_OFFSET` and friends show up in the value column in red.

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

### The command protocol

`proto/sats_command.proto` is the contract. A `SatCmd` is a oneof over
`WriteU8` / `WriteU16` / `WriteU32` / `WriteF32` / `ReadField`, each
addressing a slate field by byte offset. The board answers every command
with a `SatResponse` carrying a status and the value that actually landed.
Messages are nanopb encoded and cobs framed, one zero byte per frame.

Writes are bounds and alignment checked against `sizeof(Slate)`, so a bad
offset comes back as `BAD_OFFSET` rather than corrupting memory.

## How to run the tests

``` bash
bazel test //...     # firmware and host c++
uv run pytest        # ground tooling
```

## Formatting

``` bash
bazel run //:format            # rewrite c++ with clang-format, python with ruff
bazel run //:format -- --check # verify only, what CI runs
```

Only tracked files are formatted, so `git add` a new file before expecting
it to be touched. C++ needs clang-format 18 on the path; its output drifts
between major versions and CI pins that one.

## Run the CI checks locally

``` bash
bazel test //test:example_test --test_output=errors
bazel build --config=pico //:blink
```

## Other scripts

``` bash
uv run scripts/parse_slate.py bazel-bin/blink Slate --flat
```
