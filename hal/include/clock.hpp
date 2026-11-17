#pragma once
/**
 * Hal abstraction over time
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <stdint.h>

/**
 * Monotonic time since boot.
 */
class Clock
{
public:
    Clock() = default;
    Clock(const Clock &) = delete;
    Clock &operator=(const Clock &) = delete;

    /** Number of microseconds since boot. */
    virtual uint64_t now_us() const = 0;

    /** Blocks. Prefer polling now_us() from an update() over sleeping. */
    virtual void sleep_us(uint64_t us) = 0;

    /** Number of milliseconds since boot. Note: overflows after 49 days. */
    uint32_t now_ms() const
    {
        return static_cast<uint32_t>(now_us() / 1000);
    }

protected:
    ~Clock() = default;
};
