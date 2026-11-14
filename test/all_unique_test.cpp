#include <gtest/gtest.h>

#include <array>
#include <cstdint>

#include "common/util/all_unique.hpp"

namespace
{

/* Check on compile-time assertions and actual tests. */
static_assert(all_unique(std::array<uint32_t, 3>{36, 35, 44}));
static_assert(!all_unique(std::array<uint32_t, 3>{25, 24, 25}));

TEST(AllUniqueTest, FindsRepeats)
{
    EXPECT_TRUE(all_unique(std::array<uint32_t, 1>{7}));
    EXPECT_TRUE(all_unique(std::array<uint32_t, 4>{1, 2, 3, 4}));
    EXPECT_FALSE(all_unique(std::array<uint32_t, 4>{1, 2, 3, 1}));
    EXPECT_FALSE(all_unique(std::array<uint32_t, 2>{9, 9}));
}

} // namespace
