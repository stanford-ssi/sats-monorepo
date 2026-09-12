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

## The filesystem

Flash is a [littlefs](https://github.com/littlefs-project/littlefs)
filesystem: power loss resilient, wear levelling, and not ours to maintain.
It is not in the bazel central registry, so `MODULE.bazel` pulls v2.11.3
from its release tarball by sha256 and builds it with
`third_party/littlefs.BUILD`, which compiles the four files that make up the
filesystem and nothing from `bd/`, `tests/` or `benches/`.

Two of its build options matter here. `LFS_NO_MALLOC` means there is no
heap: every buffer it needs is handed to it, like the rest of this firmware.
`LFS_NO_DEBUG`, `LFS_NO_WARN` and `LFS_NO_ERROR` turn off its printf
logging, because the cdc port is carrying cobs framed commands and anything
printed onto it is corruption as far as the ground is concerned. Errors come
back as return codes instead.

What is ours is the wiring on either side of it:

- `common/fs/lfs_storage.hpp` is the block device littlefs asks to be
  given, filled in for a `BlockDevice`: block and offset addressing into
  byte offsets, geometry read off the device rather than hardcoded, and the
  read, program, lookahead and per-file buffers it would otherwise have
  malloc'd. It is not a layer over littlefs and wraps none of it;
  `config()` being null for a device it cannot be configured for is the
  only failure it has.
- `common/fs/lfs_files.hpp` is two convenience calls, `lfs_read_whole()`
  and `lfs_write_whole()`, because littlefs has no single call for a whole
  file and the close is the operation that commits one. An app that checks
  the write and not the close loses saves silently, so that is collapsed
  once here rather than in every app.
- `hal/pico/flash.cpp` is the chip itself, and the only pico specific part.
  It claims the top 128 KiB, erases and programs with interrupts off, since
  the flash is not answering the memory bus while that runs and every
  interrupt handler on this board lives in it, and refuses to hand out a
  region a grown firmware image has run into rather than one that works
  until the next build.

Apps use the littlefs api directly otherwise; nothing of ours wraps it, and
mounting, formatting and the decision about what to do when a mount fails
stay visible in the app rather than behind a method. littlefs's own
`DESIGN.md` and `SPEC.md` are the reference for what it guarantees. Note that `lfs_file_open()` is unusable in this build, with no
heap to take a file cache from: `lfs_file_opencfg()` with an `LfsFileBuffer`
is the way in, one per file open at a time.

`blink` uses it for one file, `settings`. At startup it mounts, formatting
first if there is nothing there yet, restores `sleep_ms` and `led_enabled`,
then counts the boot and writes that back, so `boot_count` in the slate goes
up by one every power cycle rather than starting from zero. To keep a new
rate across a reset, set it and then ask for a save:

``` bash
uv run scripts/satui.py --set sleep_ms=1000 --set save_settings=1
```

The firmware clears `save_settings` once the write has landed and leaves
`fs_error` at 0 if it worked; anything else is one of the negative
`LFS_ERR` codes from `lfs.h`. `fs_bytes_free` is what littlefs has not
allocated, counted in blocks. Saving is asked for rather than automatic
because programming flash runs with interrupts off and stops the loop for
as long as it takes.

Where the region sits depends on how big the build thinks the chip is,
which is `PICO_FLASH_SIZE_BYTES` from the board header the pico sdk picks
up. That is 2 MB as this builds today, putting the region at `0x101e0000`,
so `fs_base` in the slate is the number to read rather than one to
remember. Note that the `--define=PICO_BOARD=samwise_pico` in `.bazelrc`
does not reach the sdk under bazel, which wants
`--@pico-sdk//bazel/config:PICO_BOARD`; until that is sorted out the build
is using the `pico` board header.

`picotool load` only writes as far as the image reaches, so flashing new
firmware leaves the filesystem alone. To wipe it and watch the next boot lay
down a fresh one, using `fs_base` for the start:

``` bash
picotool erase -r 0x101e0000 0x10200000
```

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
