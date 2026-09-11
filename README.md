# SSI Sats Monorepo

## Build the example firmware

```bash
bazel build --config=pico //:blink
```

The uf2 and the elf both land in `bazel-bin/`, as `blink.uf2` and `blink`.

## How to flash a pico

The board is an RP2350 (pico 2). If it is plugged in over usb and already
running pico-sdk firmware, picotool can reboot it into BOOTSEL itself:

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

## How to send commands to a running board

`send_cmd.py` reads the field offsets out of the elf's debug info, so the
offsets always match the binary you actually flashed. It prompts for values
and writes cobs framed SatCmds to the board's usb cdc port.

``` bash
uv run scripts/send_cmd.py                     # sleep_ms, port autodetected
uv run scripts/send_cmd.py --field temperature
uv run scripts/send_cmd.py --dry-run           # print the frames, send nothing
```

At the prompt, enter a bare value to write the current field, or
`<field> <value>` to switch fields. Reading the serial port needs membership
in the `dialout` group.

## How to run the test cases

``` bash
bazel test //...
```

## Run the CI checks locally

```bash
bazel test //test:example_test --test_output=errors
bazel build --config=pico //:blink
```

## Run Python tools

```bash
uv run scripts/parse_slate.py bazel-bin/blink Slate
```
