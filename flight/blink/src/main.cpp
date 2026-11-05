#include <stdio.h>
#include "pico/stdlib.h"

#include "common/cobs/cobs.hpp"
#include "common/util/ring_buffer.hpp"
#include "common/util/queue.hpp"
#include "common/util/interval.hpp"

#include "tusb.h"

#include "proto/sats_command.pb.h"

#include "common/sat_link/sat_link.hpp"
#include "common/slate/slate_server.hpp"

#include "hal/usb_queue.hpp"
#include "hal/gpio.hpp"
#include "hal/pico/pico_gpio.hpp"
#include <optional>

#include "slate.hpp"

static Slate gSlate{};

int main()
{
    stdio_init_all();

    sleep_ms(1000);

    const uint LED_PIN = PICO_DEFAULT_LED_PIN;
    Gpio::GpioHardware led_hardware = Gpio::GpioHardware(LED_PIN);
    Gpio led_gpio = led_hardware.build();
    led_gpio.set_function(GpioFunction::Output);

    UsbQueue q{};
    SatLink<SatMsg, SatMsg> link{q, q};
    SlateServer<Slate> server{gSlate};

    Interval blink{};
    bool led_on = false;

    while (true) {
        link.update();

        /* Drain every message that arrived; the link only holds 8, so
           taking one per pass would quietly drop the rest of a burst.
           Responses get no reply; this board sends no requests of its own. */
        while (std::optional<SatMsg> msg = link.receive()) {
            if (std::optional<SatMsg> rsp = server.handle(*msg)) {
                link.send(*rsp);
            }
        }

        /* Blink on a gate rather than a sleep, so the loop keeps servicing
           commands between edges. gSlate.sleep_ms is read fresh each pass,
           so a new rate from the ground takes effect immediately. */
        if (blink.ready(to_ms_since_boot(get_absolute_time()),
                        gSlate.sleep_ms)) {
            /* The gate keeps ticking while the led is disabled, so the
               blink resumes in phase rather than wherever it stopped. */
            led_on = gSlate.led_enabled && !led_on;
            led_gpio.set(led_on);
            if (led_on)
                gSlate.cycle_counter++;
        }

    } // while(true)

} // int main
