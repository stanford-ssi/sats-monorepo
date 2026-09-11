#include <gtest/gtest.h>

TEST(ExampleTest, CheckMathWorks)
{
    EXPECT_EQ(2 * 2, 4);
}

TEST(ExampleTest, StringAssertion)
{
    EXPECT_STRNE("hello", "world");
}
