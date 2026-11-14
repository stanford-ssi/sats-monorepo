#pragma once
/**
 * Temporary implementation of PiCubed from SAMWISE.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <array>
#include <stdint.h>

#include "common/util/all_unique.hpp"

struct PicubedPins
{
    static constexpr uint32_t kLed = 25;
    static constexpr uint32_t kBurnA = 36;
    static constexpr uint32_t kBurnB = 35;
    static constexpr uint32_t kBurnRelay = 44;
};

static_assert(all_unique(std::array{PicubedPins::kLed, PicubedPins::kBurnA,
                                    PicubedPins::kBurnB,
                                    PicubedPins::kBurnRelay}),
              "picubed: a pin is used twice");
