#include "pico/stdlib.h"

#include "common/proto/sats_command.pb.h"
#include "pb_encode.h"

#include "slate.hpp"

#include <array>

static Slate gSlate{};

int main() {
    ssi_protobuf_WordCommand cmd_out = {4, 4};
    uint8_t buf[10];
    pb_ostream_t stream = pb_ostream_from_buffer(buf, sizeof(buf));
    pb_encode(&stream, ssi_protobuf_WordCommand_fields, &cmd_out);

    const uint LED_PIN = PICO_DEFAULT_LED_PIN;
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);
    while (true) {
        gSlate.cycle_count += 1;
        gpio_put(LED_PIN, 1);
        sleep_ms(250);
        gpio_put(LED_PIN, 0);
        sleep_ms(250);
    }
}
