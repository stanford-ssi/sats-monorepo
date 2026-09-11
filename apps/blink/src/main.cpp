#include <stdio.h>
#include "pico/stdlib.h"

#include "common/cobs/cobs.hpp"
#include "common/util/ring_buffer.hpp"
#include "common/util/queue.hpp"

#include "tusb.h"

#include "proto/sats_command.pb.h"

#include "common/cmd_receiver/cmd_receiver.hpp"

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
    CmdReceiver recv = CmdReceiver(q);

    while (true) {
        recv.update();
        std::optional<SatCmd> cmd = recv.get_cmd();
        if (cmd) {
            SatCmd cmd_val = cmd.value();
            uint8_t *ptr = reinterpret_cast<uint8_t*>(&gSlate);
            ptr += cmd_val.offset;
            uint32_t *int_ptr = reinterpret_cast<uint32_t*>(ptr);
            *int_ptr = cmd_val.value;
        }

        gpio_put(LED_PIN, 1);
        sleep_ms(gSlate.sleep_ms);
        gpio_put(LED_PIN, 0);
        sleep_ms(gSlate.sleep_ms);

    } // while(true)

} // int main
