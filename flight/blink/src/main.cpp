#include <stdio.h>
#include "pico/stdlib.h"

#include "common/cobs/cobs.hpp"
#include "common/util/ring_buffer.hpp"
#include "common/util/queue.hpp"
#include "common/util/interval.hpp"

#include "tusb.h"

#include "proto/sats_command.pb.h"

#include "common/rust_example/example.h"

#include "common/cmd_receiver/cmd_receiver.hpp"
#include "common/cmd_responder/cmd_responder.hpp"
#include "common/slate/slate_writer.hpp"
#include "common/fs/lfs_files.hpp"
#include "common/fs/lfs_storage.hpp"

#include "hal/flash.hpp"
#include "hal/usb_queue.hpp"
#include <optional>

#include "slate.hpp"

static Slate gSlate{};

/* The top of flash, wired up as littlefs's block device. Static rather than
   local to main: between them these carry a few pages of cache, which is a
   lot to hand a 2 KiB stack. */
static Flash gFlash{};
static LfsStorage gStorage{gFlash};
static lfs_t gLfs{};
static bool gMounted = false;

/**
 * The one file this app keeps in flash.
 *
 * The version is checked on the way back in, so a build that changed the
 * layout ignores the old contents instead of reinterpreting their bytes.
 * littlefs checksums what it stores, which proves the bytes are the ones
 * that were written; only this version says they still mean the same thing.
 */
struct Settings
{
    uint32_t version;
    uint32_t boot_count;
    uint32_t sleep_ms;
    bool led_enabled;
};

static constexpr uint32_t kSettingsVersion = 1;
static constexpr const char *kSettingsFile = "settings";

/* Filesystem trouble is reported through the slate rather than printed: the
   cdc port is carrying cobs framed commands, and stray text on it is
   something the ground has to throw away. littlefs is built with its own
   printf logging off for the same reason. */
static void report(int err)
{
    gSlate.fs_error = err;

    if (!gMounted) {
        gSlate.fs_bytes_free = 0;
        return;
    }

    /* What littlefs has allocated, which counts blocks rather than the
       bytes in them, and can overcount where blocks are shared. */
    const lfs_ssize_t used = lfs_fs_size(&gLfs);
    const lfs_config *cfg = gStorage.config();
    if (used < 0) {
        gSlate.fs_error = static_cast<int32_t>(used);
        gSlate.fs_bytes_free = 0;
    } else if (static_cast<lfs_size_t>(used) < cfg->block_count) {
        gSlate.fs_bytes_free = (cfg->block_count - used) * cfg->block_size;
    } else {
        gSlate.fs_bytes_free = 0;
    }
}

static void save_settings()
{
    if (!gMounted) {
        return;
    }

    const Settings settings{kSettingsVersion, gSlate.boot_count,
                            gSlate.sleep_ms, gSlate.led_enabled};

    const int written =
        lfs_write_whole(&gLfs, kSettingsFile, &settings, sizeof(settings));
    report(written < 0 ? written : 0);
}

/**
 * Mount the filesystem and put the saved settings into the slate.
 *
 * Every failure here is survivable: the slate already holds sensible
 * defaults, so the board blinks either way and the reason is left in
 * `fs_error` for the ground to look at.
 */
static void load_settings()
{
    const lfs_config *cfg = gStorage.config();
    if (cfg == nullptr) {
        /* No region to mount on, which on this board means the firmware
           image has grown into where it would have been. */
        report(LFS_ERR_INVAL);
        return;
    }

    int err = lfs_mount(&gLfs, cfg);
    if (err < 0) {
        /* Nothing there yet, or nothing usable. A fresh board reads this
           way, so laying a filesystem down is the normal path rather than
           the desperate one. */
        err = lfs_format(&gLfs, cfg);
        if (err >= 0) {
            err = lfs_mount(&gLfs, cfg);
        }
    }
    if (err < 0) {
        report(err);
        return;
    }
    gMounted = true;

    Settings saved{};
    const int read =
        lfs_read_whole(&gLfs, kSettingsFile, &saved, sizeof(saved));
    if (read == static_cast<int>(sizeof(saved)) &&
        saved.version == kSettingsVersion) {
        gSlate.sleep_ms = saved.sleep_ms;
        gSlate.led_enabled = saved.led_enabled;
        gSlate.boot_count = saved.boot_count;
    }

    /* Count this boot and write it straight back, so a power cycle is
       visible in the slate whether or not anything else was ever saved. */
    gSlate.boot_count++;
    save_settings();
}

int main()
{
    stdio_init_all();

    sleep_ms(1000);

    const uint LED_PIN = PICO_DEFAULT_LED_PIN;
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    UsbQueue q{};
    CmdReceiver recv{q};
    CmdResponder responder{q};
    SlateWriter<Slate> writer{gSlate};

    gSlate.fs_base = gFlash.base();
    load_settings();

    Interval blink{};
    bool led_on = false;

    while (true) {
        recv.update();

        /* Drain every command that arrived; the receiver only holds 8, so
           taking one per pass would quietly drop the rest of a burst. */
        while (std::optional<SatCmd> cmd = recv.get_cmd()) {
            responder.send(writer.apply(*cmd));
        }

        /* Saving is asked for rather than automatic. Programming flash
           stops the processor and runs with interrupts off, which is not
           something to do on every write the ground makes to the slate. */
        if (gSlate.save_settings) {
            gSlate.save_settings = false;
            save_settings();
        }

        /**
         * Test rust function call
         */
        gSlate.rust_result = rust_add(gSlate.rust_test_a, gSlate.rust_test_b);

        /* Blink on a gate rather than a sleep, so the loop keeps servicing
           commands between edges. gSlate.sleep_ms is read fresh each pass,
           so a new rate from the ground takes effect immediately. */
        if (blink.ready(to_ms_since_boot(get_absolute_time()),
                        gSlate.sleep_ms)) {
            /* The gate keeps ticking while the led is disabled, so the
               blink resumes in phase rather than wherever it stopped. */
            led_on = gSlate.led_enabled && !led_on;
            gpio_put(LED_PIN, led_on);
            if (led_on)
                gSlate.cycle_counter++;
        }

    } // while(true)

} // int main
