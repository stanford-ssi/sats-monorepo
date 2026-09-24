#pragma once
/**
 * Hal abstraction over GPIO
 * Author: Carson Lauer
 * Date: 12 September 2026
 */

#include <memory>

enum class GpioFunction
{
    Input,
    Output,
};

class Gpio
{
public:
    class GpioHardware;

    void set(bool value);

    void set_function(GpioFunction func);

private:
    GpioHardware &hardware_;

    Gpio(GpioHardware &hardware) : hardware_(hardware){};
};
