#pragma once
/**
 * Fake GPIO for tests and simulation.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <cstddef>

#include "hal/gpio.hpp"

class FakeDigitalOut final : public DigitalOut
{
public:
    explicit FakeDigitalOut(bool initial = false) : value_(initial) {}

    void set(bool value) override
    {
        if (value != value_) {
            times_changed_++;
        }
        value_ = value;
    }

    bool get() const
    {
        return value_;
    }

    /** Returns the number of times the output has changed, useful for e.g.
     * burnwire. */
    std::size_t times_changed() const
    {
        return times_changed_;
    }

private:
    bool value_;
    std::size_t times_changed_{};
};

class FakeDigitalIn final : public DigitalIn
{
public:
    explicit FakeDigitalIn(bool initial = false) : level_(initial) {}

    bool read() const override
    {
        return level_;
    }

    /** Stands in for whatever drives the pin on real hardware. */
    void drive(bool level)
    {
        level_ = level;
    }

private:
    bool level_;
};
