#include <gtest/gtest.h>

#include <expected>

#include "drivers/driver/driver.hpp"

namespace
{

/* Fails init() many times before succeeding, to test ready() logic. */
class BadDriver final : public Driver
{
public:
    explicit BadDriver(int failures) : Driver("bad"), failures_(failures) {}

private:
    std::expected<void, DriverError> do_init() override
    {
        if (failures_ > 0) {
            failures_--;
            return std::unexpected(DriverError::HwFault);
        }
        return {};
    }

    int failures_;
};

TEST(DriverTest, NotReadyUntilInitSucceeds)
{
    BadDriver d{0};
    EXPECT_FALSE(d.ready());

    EXPECT_TRUE(d.init().has_value());
    EXPECT_TRUE(d.ready());
}

TEST(DriverTest, FailedInitReportsErrorAndCanBeRetried)
{
    BadDriver d{1};

    std::expected<void, DriverError> first = d.init();
    ASSERT_FALSE(first.has_value());
    EXPECT_EQ(first.error(), DriverError::HwFault);
    EXPECT_FALSE(d.ready());

    EXPECT_TRUE(d.init().has_value());
    EXPECT_TRUE(d.ready());
}

} // namespace
