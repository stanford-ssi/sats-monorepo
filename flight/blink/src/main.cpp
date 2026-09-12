#include <stdio.h>
#include "pico/stdlib.h"

#include "common/cobs/cobs.hpp"
#include "common/util/ring_buffer.hpp"
#include "common/util/queue.hpp"
#include "common/util/interval.hpp"

#include "tusb.h"

#include "proto/sats_command.pb.h"

#include "common/cmd_receiver/cmd_receiver.hpp"
#include "common/cmd_responder/cmd_responder.hpp"
#include "common/slate/slate_writer.hpp"

#include "hal/usb_queue.hpp"
#include <optional>

#include "slate.hpp"

static Slate gSlate{};

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

    Interval blink{};
    bool led_on = false;

    while (true) {
        recv.update();

        /* Drain every command that arrived; the receiver only holds 8, so
           taking one per pass would quietly drop the rest of a burst. */
        while (std::optional<SatCmd> cmd = recv.get_cmd()) {
            responder.send(writer.apply(*cmd));
        }

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
