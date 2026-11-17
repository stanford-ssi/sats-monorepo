#pragma once
/**
 * Base class for every device driver.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <expected>
#include <string_view>

#include "drivers/driver/driver_error.hpp"

/**
 * A driver for hardware on the board.
 */
class Driver
{
public:
    Driver(const Driver &) = delete;
    Driver &operator=(const Driver &) = delete;

    /**
     * Initializes the driver.
     *
     * This method should be called once before any other driver methods are
     * used.
     */
    [[nodiscard]] std::expected<void, DriverError> init()
    {
        std::expected<void, DriverError> result = do_init();
        ready_ = result.has_value();
        return result;
    }

    bool ready() const
    {
        return ready_;
    }

    /**
     * The driver's name.
     */
    virtual std::string_view name() const = 0;

protected:
    Driver() = default;

    /**
     * Can only be destroyed by a subclass, preventing bugs with
     * destructing a generic Driver and therefore not properly
     * cleaning up the subclass.
     */
    ~Driver() = default;

private:
    virtual std::expected<void, DriverError> do_init() = 0;

    bool ready_ = false;
};
