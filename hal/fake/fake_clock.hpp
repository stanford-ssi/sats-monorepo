#pragma once
/**
 * Test clock that can be manually stepped.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <stdint.h>

#include "hal/clock.hpp"

class FakeClock final : public Clock
{
public:
    uint64_t now_us() const override
    {
        return now_us_;
    }

    /** Sleeping is faked on tests. */
    void sleep_us(uint64_t us) override
    {
        now_us_ += us;
    }

    void advance_us(uint64_t us)
    {
        now_us_ += us;
    }

    void advance_ms(uint64_t ms)
    {
        now_us_ += ms * 1000;
    }

private:
    uint64_t now_us_{};
};
