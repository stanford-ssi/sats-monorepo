#pragma once
/**
 * A generic board class that configures hardware on a build target.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <cstddef>
#include <span>

#include "hal/gpio.hpp"

#include "drivers/driver/driver.hpp"

/* Forward declare all drivers here so boards can access them. */
class BurnWire;

/**
 * Boards own every driver and provide access to them. If the driver
 * isn't present on the board, the board returns nullptr. This is a
 * design choice to avoid having to check for the board type in the app
 * and to create a unified interface for all boards.
 *
 * Make sure to check for nullptr before using a driver, as not all boards
 * have all drivers.
 */
class Board
{
public:
    Board(const Board &) = delete;
    Board &operator=(const Board &) = delete;

    /** Brings up every driver in drivers(), in list order; returns how
        many failed. One failure does not stop the rest. */
    std::size_t init()
    {
        std::size_t failed = 0;
        for (Driver *driver : drivers()) {
            if (!driver->init()) {
                failed++;
            }
        }
        return failed;
    }

    /** Every driver actually present (not nullptr) on this board. */
    virtual std::span<Driver *const> drivers()
    {
        return {};
    }

    virtual DigitalOut *led()
    {
        return nullptr;
    }

    virtual BurnWire *burn_wire()
    {
        return nullptr;
    }

protected:
    Board() = default;

    /**
     * Can only be destroyed by a subclass, preventing bugs with
     * destructing a generic Board and therefore not properly
     * cleaning up the subclass.
     */
    ~Board() = default;
};
