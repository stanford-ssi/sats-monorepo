#pragma once
/**
 * PiCubed flight board. Temporary pin map from SAMWISE.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <array>
#include <stdint.h>

#include "common/util/all_unique.hpp"
#include "hal/raspi/raspi_clock.hpp"
#include "hal/raspi/raspi_gpio.hpp"

#include "boards/board.hpp"
#include "drivers/burn_wire/burn_wire.hpp"

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

class PicubedBoard final : public Board
{
public:
    PicubedBoard()
        : burn_a_(PicubedPins::kBurnA, false),
          burn_b_(PicubedPins::kBurnB, false),
          burn_relay_(PicubedPins::kBurnRelay, false),
          burn_wire_(burn_a_, burn_b_, burn_relay_, clock_),
          led_(PicubedPins::kLed, false)
    {}

    std::span<Driver *const> drivers() override
    {
        return drivers_;
    }

    DigitalOut *led() override
    {
        return &led_;
    }

    BurnWire *burn_wire() override
    {
        return &burn_wire_;
    }

private:
    RaspiClock clock_;

    RaspiDigitalOut burn_a_;
    RaspiDigitalOut burn_b_;
    RaspiDigitalOut burn_relay_;

    BurnWire burn_wire_;
    RaspiDigitalOut led_;

    std::array<Driver *, 1> drivers_{&burn_wire_};
};
