# Sat Software Onboarding

Welcome to software! We put code **in space**!!

# Part -1: History

First, some context.

Long ago, SSI designed a CubeSat "framework" called the PyCubed. It was great,
because it was a "commercial off-the-shelf" satellite, meaning we could build it
quickly and reliably.

While much of the original design had changed up until this year, one design
decision stuck with us: CircuitPython for our flightcode.

Over time, the benefits of Python as a language began to pale in comparison to
its costs: implicit heap allocations caused random (catastrophic) errors, lack
of proper interrupt support meant lots of polling, lack of explicit static
memory allocation made the aforementioned heap allocations worse, etc.

We then created [SAMWISE](https://github.com/stanford-ssi/samwise-flight-software/), which was written in C. Now, we are using C++, to make it easier to develop.

We _also_ switched microcontrollers from the SAMD51 (which was mostly hidden
from us by CircuitPython) to the lovely RP2350 (A.K.A. the Raspberry Pi Pico 2).

What does that mean for **_you_**? Lots of opportunity to build on what you
learned in CS 106A, 106B, 107, 107E, etc. etc. and build some **real satellite
flight code**. Not only is this a _great_ learning experience, but it's
**great** on a resume! SSI software alumni have gone on to NASA, SpaceX, and
grad school ;)

We're going to use our actual flight software on a special build (`PICO`) that runs some minimal code!

# Part 0: Install

You will need to use the terminal to install some programs. If you are not
familiar with a terminal, I recommend first installing [Visual Studio
Code](https://code.visualstudio.com/). Then, you should use the VS Code
integrated terminal (tutorial
[here](https://code.visualstudio.com/docs/terminal/basics)). Ubuntu has a neat
[tutorial](https://ubuntu.com/tutorials/command-line-for-beginners#4-creating-folders-and-files) on terminal usage - ignore the Ubuntu specific stuff.

## [MacOS Only] Homebrew

On MacOS, we will use Homebrew to install everything. This is an extremely useful package manager.

Install Homebrew if you don't already have it:

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

After installing Homebrew, close and re-open your terminal.

## [Windows Only] WSL2
Windows is not very fun. Because it is built completely seperately from MacOS (which is Unix) and Linux distributions, it doesn't work properly with compiling low-level code, which is mostly tested and run on Linux.

Here are the options for running stuff on Windows:
1. `WSL2` - **Recommended**. This allows you to create a very efficient virtual machine for Linux on your Windows computer, owned by Microsoft itself. Then, you can properly do everything. 

   This does take a non-insignificant amount of disk space, but it is not that bad; and you most likely will have to set this up in the future anyway for things like low level systems, Docker, etc. if you stick to Windows. We will explain how to do this!
2. `Dual Boot Linux`! This is a very hard option, but it's a good idea if you've been interested in trying out  Linux anyway for whatever reason. 
   
   We've had very good experiences with Linux distributions in the past, as they have become way faster, more battery efficient, and just nicer to use than Microslop's Windows. Feel free to ask for help on this step, we won't document it here, but you do need a large amount of empty disk space. We can give you advice on distros, etc.
3. `Wait for Linux Boxes`. We are planning to buy Linux Boxes so that you can compile, test, and run code through actual hardware. This has not been setup yet, so we recommend trying `WSL2` first.

### Installation
WSL is very easy to setup. Simply open Windows Terminal and enter:
```powershell
wsl --install
```

This will setup and install Ubuntu on your Windows machine.

Whenever you want to access WSL, just open Windows Terminal and either type in `wsl` in the command prompt, or open a new tab with the "Ubuntu" logo for the shell.

Now, just follow the instructions for Linux!

## Git

### MacOS
```bash
brew install git
```

### Linux & WSL2
This can be done with your package manager. On Ubuntu:
```bash
sudo apt update
sudo apt install git
```

## Bazelisk
First, we need to install Bazelisk, our build system manager. 

### MacOS
You can install it on MacOS with Homebrew:

```bash
brew install bazelisk
```

### Linux & WSL2
If not on MacOS, find your binary on the [Github Releases Page](https://github.com/bazelbuild/bazelisk/releases).
* Usually, you need the `bazelisk-linux-amd64` release, which is for Intel/AMD chips.
* If you have a very new and cool RISC-V chip (if you don't know what this means, you most likely don't have one!), then aim for `-arm64` instead.

> Tip: You can copy the link of the release you want and type `wget [your-link-here]`, for example `wget https://github.com/bazelbuild/bazelisk/releases/download/v1.29.0/bazelisk-linux-amd64`. This will automatically download the file in your current directory!

You can then rename this binary to `bazelisk` and move it somewhere where apps are stored. 
* On Linux, we recommend `/usr/local/bin/bazelisk`. You can do this with `sudo mv [source] [destination]` (`sudo` is required for `/usr/local/bin`).

### Verification
To make sure this worked, open a new terminal and type `bazelisk`. It should try downloading Bazel 9.2.0. You can stop this by pressing CTRL+C, as this is not the correct version.

If you get a permission denied error, use:
```
sudo chmod +x /usr/local/bin/bazelisk
```
This will tell Linux that this is an executable file. Then, try again.

## Picotool

This is technically optional, but highly recommended for ease of use. Picotool essentially allows you to work directly with the pico without unplugging/plugging/pressing buttons, which can save a lot of time.

### MacOS

`brew install picotool` should work.

### Linux & WSL2

You can find binaries at the [`pico-sdk-tools Github`](https://github.com/raspberrypi/pico-sdk-tools/releases/latest), similar to `bazelisk`. You may need to click `Show all assets` to get the correct version.
* Usually, you need the `picotool-<version>-x86_64-lin` release, which is for Intel/AMD chips.
* If you have a very new and cool RISC-V chip (if you don't know what this means, you most likely don't have one!), then aim for `aarch64` instead.

> Tip: This is a `.tar.gz` zipped folder. In order to unzip from the command line, you can do `tar -xvzf [filename]`. `-x` means extract, `-v` means verbose (more information about whats being unzipped), `-z` allows you to remove the gzip part (`.gz`), and `-f` specifies the filename.

You can use the `picotool` binary seperately, moving it into the corresponding folder.
* On Linux, we recommend `/usr/local/bin/picotool`.

### Verification
Type in `picotool`, and it should give you a bunch of help text. If you have access to a RP2350 or any other Raspberry Pi device, plug it into your computer and type `picotool info`. You should get information about this chip. (You may have to do `sudo` on Linux).

You may have to do `sudo chmod +x /usr/local/bin/picotool` like above.

## Tio

This software allows you to communicate with a pico and read its logs.

### MacOS

`brew install tio`

### Linux & WSL

Run `sudo snap install tio --classic`.

If you don't have `snap`, install it, for example, on Ubuntu:

```bash
sudo apt update
sudo apt install snapd
```

Note you may have to add snap's bin to path - so in `~/.bashrc` or `~/.zshrc` (If you don't know what `zsh` is, use `.bashrc`):

```bash
export PATH="/snap/bin:$PATH"
```

If you have opinions about snap or don't really want to install it, you can also download from tio's [GitHub Releases](https://github.com/tio/tio/releases/latest).

## GCC
Because of beloved Bazel, we only need to install basic gcc! (Don't worry what this means, it just means so much less work :D).

### MacOS
You know the drill:
```bash
brew install gcc
```

### Linux & WSL2
On Ubuntu:
```bash
sudo apt install build-essential
```

## Moving on

Now we should be done with installation! Here are our
tentative steps:

1. Build the project
2. Drag and drop to flash onto the PICO
3. Use `picotool` to flash onto the PICO
   - If on WSL, use `usbipd`
4. Finally, use `tio` to listen

# Part 1: Bazel, Building & Project Structure

Look around the `sats-monorepo` repository, and look for `BUILD.bazel` or any `*.bazel` files. Try to understand them - reading through can be really helpful.

In general:

- `bazel` is a build system that allows you to automatically link and compile files easily, similar to `cmake` (but MUCH better!)
- Features of `bazel`: tests, caching (so we don't have to compile everything every time), `genrule`s (to get into later), and much more
- `.bazelrc` is where we configure `bazel`, including the different build profiles.
  - We will focus on `pico`, which is what we are playing with, but `picubed-flight` is the final version that will go onto our satellite!
  - We also link `pico-sdk` here, which allows us to use the library with the pico/raspi/etc.
- `BUILD.bazel` specifies _targets_, i.e. a component that needs to be compiled, along with its _dependencies_, which are the subcomponents it requires to function.
  - The root `BUILD.bazel` is our actual binary, and depends on essentially all code in the repository (of course!)
  - Then, each path in `dependencies` as shown in `//BUILD.bazel` has its own `BUILD.bazel` file - for example, `//src/tasks/print/BUILD.bazel` has a `print_task`, which simply prints a message every few seconds, and it depends on `logger`, for example.
  - We can use `select` to change dependencies based on the current configuration - this is how we change loggers, for example, if we are on a computer or if we are on `pico`.

Please ask if you have any questions!

# Part 2: First PICO Build

All microcontrollers come with some pins you can turn on and off, communicate
over, etc. These pins are called _general purpose input/output pins_ or GPIO
pins. You can configure them from software.

Generally, these are the steps:

- Initialize the pin
- Set the direction (input or output) of the pin
- Write (if it's output) or read (if it's input) from the pin

Some GPIO pins are connected to physical wires on the board, whereas others are
routed to built-in components. For this example, we are going to use pin 25,
which is routed to an LED on the board. This magic number is provided with a
convenient name in the SDK: `PICO_DEFAULT_LED_PIN`.

Microcontrollers also come with some timing facilities. For now, all we need to
use is the sleeping methods, which are exactly like the ones from Python.

## Git

You should create a clone of [the onboarding repository](https://github.com/megargayu/ssi-onboarding-26/) using VSCode
(or a git client of your choice). If you are using VSCode, they provide a
[tutorial](https://code.visualstudio.com/docs/sourcecontrol/intro-to-git) on how
to do this.

The rest of this guide takes place from within this folder/repository.

There is a lot of stuff in there, so read its `README` to understand it better!

## Code

Put this in `src/main.cpp`:

```c
#include "pico/stdlib.h"

int main() {
    stdio_usb_init();

    gpio_init(PICO_DEFAULT_LED_PIN);
    gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);
    while (1) {
        gpio_put(PICO_DEFAULT_LED_PIN, 0);
        sleep_ms(250);
        gpio_put(PICO_DEFAULT_LED_PIN, 1);
        sleep_ms(1000);
    }
}
```

## Building

Run:

```bash
bazel build :ssi-onboarding-26 --config=pico
```

Which should generate a bunch of folders, including most importantly `bazel-bin/ssi-onboarding-26.uf2`, which is the actual binary! This is essentially the same command for the monorepo, except we use a different target name and various configurations, as explained briefly above (`.bazelrc`).

## Uploading

1. Unplug your PICO
2. Hold the BOOT button on your PICO
3. While holding, plug it in. A window should pop up with a directory that corresponds to the PICO, or it should generally be available in Finder/Windows Explorer/etc. On Mac, a drive called "RP2350" or similar should appear on your desktop.
4. Copy `bazel-bin/ssi-onboarding-26.uf2` into the drive that shows up.
5. The folder should close almost immediately, and after the pico reboots, the light should start to blink!

If all of this works, success!

## Uploading (Cool version)

If you are not all about that drag-and-drop life:

1. Unplug your PICO
2. Hold the BOOT button on your PICO
3. While holding, plug it in. A window should pop up with a directory that corresponds to the PICO, or it should generally be available in Finder/Windows Explorer/etc. On Mac, a drive called "RP2350" or similar should appear on your desktop.
4. In the repository, run:

   ```bash
   picotool load bazel-bin/ssi-onboarding-26.uf2 -f
   ```

   You may have to click the "RESET" button after doing this - but the LED should start blinking!

   Note that you may have to put `sudo` at the beginning if it doesn't work.

   Additionally, if you are on `WSL`, you must use `usbipd` (see instructions below)

Note this is cool but also useful. You no longer need to reattach and attach the stick now. If you repeat step 5 again and again, it will automatically force the pico to reboot and then flash the new code. Try it out yourself - edit `main.cpp` and only run step 4 again! (Make sure to build first!).

## WSL2 Integration

If you are on WSL2, you also have to do an additional step:

Your pico is only accessible from Windows by default. In order for WSL to see it, you have to tell Windows to link it into WSL.

Every time you connect the Pico and either want to `tio` or `picotool`, therefore:

1. Unplug your PICO
2. Hold the BOOT button on your PICO
3. While holding, plug it in. A window should pop up with a directory that corresponds to the PICO, or it should generally be available in Finder/Windows Explorer/etc. On Mac, a drive called "RP2350" or similar should appear on your desktop.
4. From powershell, run `usbipd list`. You should see a bunch of stuff, including:

```
BUSID  VID:PID    DEVICE                                                        STATE
2-3    2e8a:000f  USB Mass Storage Device, RP2350 Boot                          Not shared
```

Each `BUSID` is a port on your computer. Therefore, it usually is the same if you plug it into the same port, but can change around otherwise.

5. If `STATE == Not shared`, then run `usbipd bind --busid {your-bus-id}`. For example, I would use `usbipd bind --busid 2-3` for myself. Usually, you only need to do this once, unless you change ports, update, etc.

6. Now that state is shared, run:

   ```powershell
   usbipd attach --wsl --busid {your-bus-id} --auto-attach
   ```

   It should output like:

   ```
   usbipd: info: Using WSL distribution 'Ubuntu' to attach; the device will be available in all WSL 2 distributions.
   usbipd: info: Loading vhci_hcd module.
   usbipd: info: Detected networking mode 'nat'.
   usbipd: info: Using IP address 172.17.192.1 to reach the host.
   usbipd: info: Starting endless attach loop; press Ctrl+C to quit.
   WSL Monitoring host 172.17.192.1 for BUSID: 2-3
   WSL 2026-04-08 17:39:21 Device 2-3 is available. Attempting to attach...
   WSL 2026-04-08 17:39:21 Attach command for device 2-3 succeeded.
   ```

   And also make the signature Windows detach noise (indicating it is no longer attached to Windows).

   This will automatically repeatedly attach your pico to WSL, until you quit the program (i.e. CTRL+C). So if you reboot or reflash any software, it will keep trying to attach your pico to WSL.

7. Now, `picotool info` (or `sudo picotool info`) should say something like:
   ```
   Program Information
   binary start:  0x10000000
   binary end:    0x10003cd4
   target chip:   RP2350
   image type:    ARM Secure
   ```
   And running step 5 in "Uploading (Cool version)" should now produce a blinking LED! Note that it will make the attach/detach noise a lot of times as the `--auto-attach` in the Powershell window will force it to attach to WSL as soon as possible. This may be annoying; you may have to deal with it :(.

## Reading from PICO

What if we want to read logs in real time?

1. Now, let's edit `main.cpp` to actually log a counter:

   ```c
   #include "pico/stdlib.h"
   #include "pico/printf.h"

   int main() {
       stdio_usb_init();
       int counter = 0;

       gpio_init(PICO_DEFAULT_LED_PIN);
       gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);
       while (1) {
           gpio_put(PICO_DEFAULT_LED_PIN, 0);
           sleep_ms(250);
           gpio_put(PICO_DEFAULT_LED_PIN, 1);
           sleep_ms(1000);

           printf("Hello, world! Our counter is: %d\n", counter);
           counter++;
       }
   }
   ```

2. Now, before we flash, let's setup `tio` by running (note you may have to add `sudo` to the start of any of these commands if you get a "permission denied"):
   - Linux/WSL: It should be `tio /dev/ttyACM0`. If not, try repeating similar steps to Mac below, or just looking for an item under `/dev/` that appears when you plug in the pico.
   - Mac: Try typing `tio /dev/tty.`, then pressing the "TAB" button. You should see a list of items appear - type in the item that starts with `usbmodem` and ends with some number.

     If there are multiple options, try pressing tab before you plug in, and then pressing it after, and seeing which item appeared (which should be the correct one).

     If nothing appears, but your pico is flashing, something is wrong with your port. Try using a different cord or flipping the USB-C Cable (yes, that sometimes works)!

3. Now, either use method (a) or the cool version to build and flash the new code onto the pico.
4. You should see something like this!:

   ```
   [17:56:05.115] Waiting for tty device..
   [17:56:09.122] Connected to /dev/ttyACM0
   Hello, world! Our counter is: 2
   Hello, world! Our counter is: 3
   Hello, world! Our counter is: 4
   Hello, world! Our counter is: 5
   Hello, world! Our counter is: 6
   Hello, world! Our counter is: 7
   Hello, world! Our counter is: 8
   Hello, world! Our counter is: 9
   Hello, world! Our counter is: 10
   ```

   Note that sometimes the first few logs are not available as `tio` connects after the code already started running on the pico.


# Part 3: What's next?

You've successfully been onboarded! Now, I would suggest trying to get an understanding of the monorepo. Look through files and figure out what goes where. We will talk more about this later!
