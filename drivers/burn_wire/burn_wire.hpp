#pragma once
/**
 * Burn wire implementation.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <expected>

#include "hal/clock.hpp"
#include "hal/gpio.hpp"

#include "drivers/driver/driver.hpp"
#include "drivers/driver/driver_error.hpp"

/**
 * STUB: not implemented yet. init() always fails, so the driver never
 * becomes ready and the board's init() counts it as one failure.
 */
class BurnWire final : public Driver
{
public:
    BurnWire(DigitalOut &a, DigitalOut &b, DigitalOut &relay, Clock &clock)
        : Driver("burn_wire"), a_(a), b_(b), relay_(relay), clock_(clock)
    {}

private:
    std::expected<void, DriverError> do_init() override
    {
        return std::unexpected(DriverError::NotReady);
    }

    /* Unused until the driver is implemented. */
    [[maybe_unused]] DigitalOut &a_;
    [[maybe_unused]] DigitalOut &b_;
    [[maybe_unused]] DigitalOut &relay_;
    [[maybe_unused]] Clock &clock_;
};
