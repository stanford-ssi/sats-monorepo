/**
 * Author: Carson Lauer
 * Date: 9 September 2026
 */

#include <stdint.h>

#include "hal/usb_queue.hpp"

#include "tusb.h"

UsbQueue::UsbQueue()
{
    tusb_init();
}

bool UsbQueue::push(const uint8_t &item)
{
    if (tud_cdc_write_char(item) != 1) {
        /* The cdc fifo is full. Kick what is already in it so the next
           attempt has somewhere to land; this byte is dropped. */
        tud_cdc_write_flush();
        return false;
    }

    /* Bytes sit in the cdc fifo until something flushes them, but a flush
       per byte spends a usb transaction on each one. Queue has no flush in
       its interface, so we lean on the framing instead: a zero byte is the
       cobs delimiter that ends a frame, which is exactly when the whole
       response should go out. */
    if (item == 0) {
        tud_cdc_write_flush();
    }
    return true;
}

bool UsbQueue::pop(uint8_t &item)
{
    int32_t c = tud_cdc_read_char();
    if (c < 0) {
        return false; // nothing buffered
    }
    item = static_cast<uint8_t>(c);
    return true;
}

bool UsbQueue::empty() const
{
    return tud_cdc_available() == 0;
}
