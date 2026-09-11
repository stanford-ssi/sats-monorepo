#include <gtest/gtest.h>

#include <cstdint>

#include "common/util/interval.hpp"

namespace
{

TEST(IntervalTest, FiresOncePerPeriod)
{
    Interval gate{};

    EXPECT_FALSE(gate.ready(5, 10)); // not yet
    EXPECT_TRUE(gate.ready(10, 10)); // exactly on the boundary
    EXPECT_FALSE(gate.ready(19, 10));
    EXPECT_TRUE(gate.ready(20, 10));
}

TEST(IntervalTest, DoesNotFireTwiceForOneTick)
{
    Interval gate{};

    EXPECT_TRUE(gate.ready(100, 10));
    EXPECT_FALSE(gate.ready(100, 10)); // polled again on the same millisecond
}

TEST(IntervalTest, CatchesUpAfterALateCall)
{
    Interval gate{};

    /* A loop that stalled past several periods gets one edge, not a burst
       of backlogged ones, and the phase restarts from when it noticed. */
    EXPECT_TRUE(gate.ready(1000, 10));
    EXPECT_FALSE(gate.ready(1005, 10));
    EXPECT_TRUE(gate.ready(1010, 10));
}

TEST(IntervalTest, PeriodCanChangeBetweenCalls)
{
    Interval gate{};

    EXPECT_TRUE(gate.ready(500, 500));
    /* The ground drops the period; the shorter one applies right away. */
    EXPECT_TRUE(gate.ready(510, 10));
    EXPECT_FALSE(gate.ready(515, 10));
}

TEST(IntervalTest, APeriodOfZeroFiresEveryCall)
{
    Interval gate{};

    EXPECT_TRUE(gate.ready(7, 0));
    EXPECT_TRUE(gate.ready(7, 0));
}

TEST(IntervalTest, SurvivesTheMillisecondCounterWrapping)
{
    Interval gate{};

    const uint32_t before_wrap = 0xFFFFFFFB; // 4 ms short of wrapping
    EXPECT_TRUE(gate.ready(before_wrap, 10));

    /* 9 ms later the counter has wrapped through zero. Unsigned arithmetic
       still gives the right elapsed time, so this must not fire early and
       must not stall for another 49 days. */
    EXPECT_FALSE(gate.ready(4, 10));
    EXPECT_TRUE(gate.ready(5, 10));
}

} // namespace
