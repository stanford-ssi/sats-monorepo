#include <expected>

#include <gtest/gtest.h>

static_assert(__cplusplus >= 202302L, "C++23 is required");

TEST(ExampleTest, CheckMathWorks)
{
    EXPECT_EQ(2 * 2, 4);
}

TEST(ExampleTest, StringAssertion)
{
    EXPECT_STRNE("hello", "world");
}

TEST(ExampleTest, Cpp23Expected)
{
    auto half = [](int x) -> std::expected<int, const char *> {
        if (x % 2 != 0) {
            return std::unexpected("odd");
        }
        return x / 2;
    };
    EXPECT_EQ(half(4).value(), 2);
    EXPECT_STREQ(half(3).error(), "odd");
}
