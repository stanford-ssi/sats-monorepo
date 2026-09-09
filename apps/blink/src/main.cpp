#include <stdio.h>
#include "pico/stdlib.h"

#include "cobs.hpp"
#include "ring_buffer.hpp"

#include "tusb.h"

#include "proto/sats_command.pb.h"

#include "cmd_receiver.hpp"

#include "slate.hpp"

static Slate gSlate{};

int main()
{
    stdio_init_all();

    sleep_ms(1000);

    const uint LED_PIN = PICO_DEFAULT_LED_PIN;
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);
    CmdReceiver recv = CmdReceiver();
    Queue<uint8_t> q = Queue<uint8_t>();

    while (true) {
        recv.update(q);
        recv.get_cmd();

        gpio_put(LED_PIN, 1);
        sleep_ms(gSlate.sleep_ms);
        gpio_put(LED_PIN, 0);
        sleep_ms(gSlate.sleep_ms);

    } // while(true)

} // int main
