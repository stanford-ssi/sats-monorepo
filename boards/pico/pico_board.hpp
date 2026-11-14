#pragma once
/**
 * Raspberry Pi Pico 2 dev board.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include "hal/raspi/raspi_gpio.hpp"

#include "boards/board.hpp"

class PicoBoard final : public Board
{
public:
    PicoBoard();

    DigitalOut *led() override
    {
        return &led_;
    }

private:
    RaspiDigitalOut led_;
};
