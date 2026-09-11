#pragma once
/**
 * Author: Carson Lauer
 * Date: 10 September 2026
 */

#include <stdint.h>

/**
 * A periodic gate for a polling loop.
 *
 * `ready()` comes back true once per period and false every other time it
 * is called, so a loop can pace work without sleeping in it. Sleeping is
 * what we are avoiding: a blocking delay in the main loop also delays
 * answering whatever arrives during it.
 *
 * The clock is passed in rather than read here, which keeps this free of
 * any hardware dependency and testable on the host.
 */
class Interval
{
public:
    /**
     * True once `period_ms` has elapsed since this last returned true.
     *
     * The period is an argument rather than state so it can change between
     * calls: the ground can write a new blink rate into the slate and the
     * next call simply uses it, with nothing to keep in sync.
     *
     * The subtraction is unsigned, so it stays correct when a millisecond
     * counter wraps, which a uint32_t one does after 49 days of uptime.
     */
    bool ready(uint32_t now_ms, uint32_t period_ms)
    {
        if (now_ms - last_ms_ < period_ms) {
            return false;
        }
        last_ms_ = now_ms;
        return true;
    }

private:
    uint32_t last_ms_{};
};
