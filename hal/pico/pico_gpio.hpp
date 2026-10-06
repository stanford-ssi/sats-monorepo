#pragma once
#include "hal/gpio.hpp"
#include "pico/stdlib.h"

class Gpio::GpioHardware
{
public:
    GpioHardware(uint32_t pin) : pin_(pin)
    {
        gpio_init(pin_);
    }

    Gpio build()
    {
        return Gpio(*this);
    }

    uint32_t pin()
    {
        return pin_;
    }

private:
    uint32_t pin_;
};

void Gpio::set(bool value)
{
    gpio_put(hardware_.pin(), value);
}

void Gpio::set_function(GpioFunction func)
{
    switch (func) {
    case GpioFunction::Input: gpio_set_dir(hardware_.pin(), GPIO_IN); break;
    case GpioFunction::Output: gpio_set_dir(hardware_.pin(), GPIO_OUT); break;
    default: break;
    }
}
