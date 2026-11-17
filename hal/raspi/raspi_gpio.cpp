/**
 * Author: Carson Lauer, Ayush Garg
 * Date: 31 October 2026
 */

#include "hal/raspi/raspi_gpio.hpp"

#include "hardware/gpio.h"

RaspiDigitalOut::RaspiDigitalOut(uint32_t pin, bool initial) : pin_(pin)
{
    gpio_init(pin_);
    /* Set the level before the direction so the pin doesn't grab a random
     * state. */
    gpio_put(pin_, initial);
    gpio_set_dir(pin_, GPIO_OUT);
}

void RaspiDigitalOut::set(bool value)
{
    gpio_put(pin_, value);
}

RaspiDigitalIn::RaspiDigitalIn(uint32_t pin, Pull pull) : pin_(pin)
{
    /* gpio_init leaves the pin an input. */
    gpio_init(pin_);
    gpio_set_pulls(pin_, pull == Pull::Up, pull == Pull::Down);
}

bool RaspiDigitalIn::read() const
{
    return gpio_get(pin_);
}
