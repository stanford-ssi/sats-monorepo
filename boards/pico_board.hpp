#pragma once
/**
 * Raspberry Pi Pico 2 dev board.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <array>
#include <stdint.h>

#include "common/util/all_unique.hpp"
#include "hal/raspi/raspi_gpio.hpp"

#include "boards/board.hpp"

struct PicoPins
{
    static constexpr uint32_t kLed = 25;
};

static_assert(all_unique(std::array{PicoPins::kLed}),
              "pico: a pin is used twice");

class PicoBoard final : public Board
{
public:
    PicoBoard() : led_(PicoPins::kLed, false) {}

    DigitalOut *led() override
    {
        return &led_;
    }

private:
    RaspiDigitalOut led_;
};
