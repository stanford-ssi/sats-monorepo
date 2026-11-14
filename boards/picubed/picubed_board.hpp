#pragma once
/**
 * PiCubed flight board.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <array>

#include "hal/raspi/raspi_clock.hpp"
#include "hal/raspi/raspi_gpio.hpp"

#include "boards/board.hpp"
#include "drivers/burn_wire/burn_wire.hpp"

class PicubedBoard final : public Board
{
public:
    PicubedBoard();

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
