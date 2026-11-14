#pragma once
/**
 * RP2350 system timer
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <stdint.h>

#include "hal/clock.hpp"

class RaspiClock final : public Clock
{
public:
    uint64_t now_us() const override;

    void sleep_us(uint64_t us) override;
};
