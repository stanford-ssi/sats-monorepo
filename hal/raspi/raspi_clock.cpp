/**
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include "hal/raspi/raspi_clock.hpp"

#include "pico/time.h"

uint64_t RaspiClock::now_us() const
{
    return to_us_since_boot(get_absolute_time());
}

void RaspiClock::sleep_us(uint64_t us)
{
    ::sleep_us(us);
}
