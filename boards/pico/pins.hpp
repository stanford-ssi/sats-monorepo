#pragma once
/**
 * Raspberry Pi Pico 2 dev board pin map. Every pin the board uses is
 * listed here and nowhere else.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <array>
#include <stdint.h>

#include "common/util/all_unique.hpp"

struct PicoPins
{
    static constexpr uint32_t kLed = 25;
};

static_assert(all_unique(std::array{PicoPins::kLed}),
              "pico: a pin is used twice");
