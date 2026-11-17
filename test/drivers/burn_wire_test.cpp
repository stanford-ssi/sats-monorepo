#include <gtest/gtest.h>

#include "drivers/burn_wire/burn_wire.hpp"
#include "hal/fake/fake_clock.hpp"
#include "hal/fake/fake_gpio.hpp"

namespace
{

/* TODO: Write real tests. */
TEST(BurnWireStubTest, InitFailsAndLeavesDriverNotReady)
{
    FakeDigitalOut a{false};
    FakeDigitalOut b{false};
    FakeDigitalOut relay{false};
    FakeClock clock{};
    BurnWire burn{a, b, relay, clock};

    EXPECT_EQ(burn.init().error(), DriverError::NotReady);
    EXPECT_FALSE(burn.ready());
    /* The stub never switches anything on. */
    EXPECT_EQ(a.times_changed(), 0u);
    EXPECT_EQ(b.times_changed(), 0u);
    EXPECT_EQ(relay.times_changed(), 0u);
}

} // namespace
