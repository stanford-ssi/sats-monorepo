/**
 * Author: Carson Lauer
 * Date: 9 September 2026
 */

#include <stdint.h>

#include "hal/usb_queue.hpp"

#include "tusb.h"

UsbQueue::UsbQueue() {
    tusb_init();
}

bool UsbQueue::push(const uint8_t& item) {
    return tud_cdc_write_char(item) == 1;
}

bool UsbQueue::pop(uint8_t& item) {
    int32_t c = tud_cdc_read_char();
    if (c < 0) {
        return false; // nothing buffered
    }
    item = static_cast<uint8_t>(c);
    return true;
}

bool UsbQueue::empty() const {
    return tud_cdc_available() == 0;
}



