#pragma once
/**
 * RP2350 gpio
 * Author: Carson Lauer, Ayush Garg
 * Date: 31 October 2026
 */

#include <stdint.h>

#include "hal/gpio.hpp"

class RaspiDigitalOut final : public DigitalOut
{
public:
    RaspiDigitalOut(uint32_t pin, bool initial);

    void set(bool value) override;

private:
    uint32_t pin_;
};

/** Raspi-specific pull-up/pull-down settings for internal resistors. */
enum class Pull
{
    None,
    Up,
    Down,
};

class RaspiDigitalIn final : public DigitalIn
{
public:
    RaspiDigitalIn(uint32_t pin, Pull pull);

    bool read() const override;

private:
    uint32_t pin_;
};
