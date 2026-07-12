#include <stdio.h>
#include "pico/stdlib.h"

#include "cobs.hpp"

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
    uint8_t buf[64];
    while (true) {
        tud_task();
        gpio_put(LED_PIN, 1);
        sleep_ms(gSlate.sleep_ms);
        gpio_put(LED_PIN, 0);
        sleep_ms(gSlate.sleep_ms);
        if (tud_cdc_available()) {
            uint32_t count = tud_cdc_read(buf, sizeof(buf));
            tud_cdc_write(buf, count);
            tud_cdc_write_flush();
        }
    }
}
