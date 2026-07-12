#include <stdio.h>
#include "pico/stdlib.h"

#include "cobs.hpp"
#include "RingBuffer.hpp"

#include "tusb.h"

#include "proto/sats_command.pb.h"
#include "pb_encode.h"

#include "slate.hpp"

static Slate gSlate{};

int main() {
    stdio_init_all();

    sleep_ms(1000);

    const uint LED_PIN = PICO_DEFAULT_LED_PIN;
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);
    static RingBuffer<uint8_t, 256> usb_rx_rb;
    while (true) {
        int c;
        if (tud_cdc_available()) {
            while ((c = tud_cdc_read_char()) >= 0) {
                if (!usb_rx_rb.push(static_cast<uint8_t>(c))) {
                    // buffer full — byte dropped, consider handling/logging this
                    break;
                }
            }
        }
        tud_task();
        gpio_put(LED_PIN, 1);
        sleep_ms(gSlate.sleep_ms);
        gpio_put(LED_PIN, 0);
        sleep_ms(gSlate.sleep_ms);

    } // main whil
} // int main
