/**
 * Author: Carson Lauer
 * Date: 25 October 2026
 */
#include "common/slate/slate_server.hpp"

#include <cstdint>
#include <cstring>

#include "gtest/gtest.h"

namespace
{

/* A stand in for the flight slate with fields of every width, laid out so
   the offsets below are stable. */
struct TestSlate
{
    uint8_t flag{};
    uint8_t mode{};
    uint16_t counter{};
    uint32_t sleep_ms{};
    float temperature{};
    int8_t trim{};
    uint64_t uptime_us{};
};

constexpr uint32_t kFlag = 0;
constexpr uint32_t kMode = 1;
constexpr uint32_t kCounter = 2;
constexpr uint32_t kSleepMs = 4;
constexpr uint32_t kTemperature = 8;
constexpr uint32_t kTrim = 12;
constexpr uint32_t kUptimeUs = 16;

static_assert(offsetof(TestSlate, flag) == kFlag, "");
static_assert(offsetof(TestSlate, mode) == kMode, "");
static_assert(offsetof(TestSlate, counter) == kCounter, "");
static_assert(offsetof(TestSlate, sleep_ms) == kSleepMs, "");
static_assert(offsetof(TestSlate, temperature) == kTemperature, "");
static_assert(offsetof(TestSlate, trim) == kTrim, "");
static_assert(offsetof(TestSlate, uptime_us) == kUptimeUs, "");
static_assert(sizeof(TestSlate) == 24, "");

SatMsg request(SatMsgType type, uint32_t offset, uint32_t width,
               uint64_t value = 0)
{
    SatMsg msg = SatMsg_init_zero;
    msg.type = type;
    msg.offset = offset;
    msg.width = static_cast<Width>(width); // any value, valid or not
    msg.value = value;
    return msg;
}

SatMsg write(uint32_t offset, uint32_t width, uint64_t value)
{
    return request(SatMsgType_SAT_MSG_TYPE_WRITE, offset, width, value);
}

SatMsg read(uint32_t offset, uint32_t width)
{
    return request(SatMsgType_SAT_MSG_TYPE_READ, offset, width);
}

uint32_t bits_of(float value)
{
    uint32_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    return bits;
}

class SlateServerTest : public ::testing::Test
{
protected:
    TestSlate slate_{};
    SlateServer<TestSlate> server_{slate_};

    /* Every request is answered, so unwrap here and keep the tests terse. */
    SatMsg handle(const SatMsg &msg)
    {
        std::optional<SatMsg> rsp = server_.handle(msg);
        EXPECT_TRUE(rsp.has_value());
        return rsp.value_or(SatMsg{});
    }

    Status status_of(const SatMsg &msg)
    {
        return handle(msg).status;
    }
};

TEST_F(SlateServerTest, AWriteLandsAndIsConfirmed)
{
    SatMsg rsp = handle(write(kSleepMs, 4, 0xdeadbeef));

    EXPECT_EQ(slate_.sleep_ms, 0xdeadbeefu);
    EXPECT_EQ(rsp.type, SatMsgType_SAT_MSG_TYPE_WRITE_RESPONSE);
    EXPECT_EQ(rsp.status, Status_STATUS_OK);
    EXPECT_EQ(rsp.offset, kSleepMs);
    EXPECT_EQ(rsp.width, Width_WIDTH_4_BYTES);
    EXPECT_EQ(rsp.value, 0xdeadbeefu);
}

TEST_F(SlateServerTest, AReadReturnsTheBytesAndLeavesThemAlone)
{
    slate_.counter = 0x0102;

    SatMsg rsp = handle(read(kCounter, 2));

    EXPECT_EQ(rsp.type, SatMsgType_SAT_MSG_TYPE_READ_RESPONSE);
    EXPECT_EQ(rsp.status, Status_STATUS_OK);
    EXPECT_EQ(rsp.value, 0x0102u);
    EXPECT_EQ(slate_.counter, 0x0102);
}

TEST_F(SlateServerTest, EveryWidthTouchesExactlyItsOwnBytes)
{
    /* Fill the neighbours so a spill in either direction would show. */
    slate_.flag = 0x11;
    slate_.counter = 0x2222;
    slate_.trim = 0x33;

    handle(write(kMode, 1, 0xAB));
    EXPECT_EQ(slate_.mode, 0xAB);
    EXPECT_EQ(slate_.flag, 0x11);
    EXPECT_EQ(slate_.counter, 0x2222);

    handle(write(kUptimeUs, 8, 0x0123456789ABCDEFull));
    EXPECT_EQ(slate_.uptime_us, 0x0123456789ABCDEFull);
    EXPECT_EQ(slate_.trim, 0x33);
}

TEST_F(SlateServerTest, AnOversizedValueIsTruncatedAndTheReplySaysSo)
{
    SatMsg rsp = handle(write(kFlag, 1, 0x1ff));

    EXPECT_EQ(slate_.flag, 0xff);
    EXPECT_EQ(slate_.mode, 0);   // truncation must not spill into the neighbour
    EXPECT_EQ(rsp.value, 0xffu); // the value that actually landed
}

TEST_F(SlateServerTest, BytesAreCopiedNotConverted)
{
    /* The server has no idea this is a float or that one is signed; the
       raw bits go in and come back out untouched. */
    handle(write(kTemperature, 4, bits_of(-0.0f)));
    EXPECT_EQ(bits_of(slate_.temperature), 0x80000000u);

    handle(write(kTrim, 1, 0xff));
    EXPECT_EQ(slate_.trim, -1);
    EXPECT_EQ(handle(read(kTrim, 1)).value, 0xffu); // not sign extended
}

TEST_F(SlateServerTest, ResponsesAndNonsenseGetNoReply)
{
    /* The answer to a request we sent is not a request to answer. */
    EXPECT_FALSE(
        server_.handle(request(SatMsgType_SAT_MSG_TYPE_READ_RESPONSE, 0, 1)));
    EXPECT_FALSE(
        server_.handle(request(SatMsgType_SAT_MSG_TYPE_WRITE_RESPONSE, 0, 1)));
    EXPECT_FALSE(
        server_.handle(request(SatMsgType_SAT_MSG_TYPE_UNSPECIFIED, 0, 1)));
    EXPECT_FALSE(server_.handle(request(static_cast<SatMsgType>(99), 0, 1)));
}

TEST_F(SlateServerTest, UnsupportedWidthsAreRejected)
{
    const TestSlate before = slate_;

    for (uint32_t width : {0u, 3u, 5u, 16u, 0xffffffffu}) {
        SatMsg rsp = handle(write(0, width, 0xffffffff));
        EXPECT_EQ(rsp.status, Status_STATUS_BAD_WIDTH) << "width " << width;
        EXPECT_EQ(rsp.value, 0u);
    }
    EXPECT_EQ(status_of(read(0, 3)), Status_STATUS_BAD_WIDTH);

    EXPECT_EQ(std::memcmp(&slate_, &before, sizeof(TestSlate)), 0);
}

TEST_F(SlateServerTest, OffsetPastTheEndIsRejected)
{
    const TestSlate before = slate_;

    /* One past the last byte, and the last byte of a u32 hanging off the end.
     */
    EXPECT_EQ(status_of(write(sizeof(TestSlate), 1, 1)),
              Status_STATUS_BAD_ADDRESS);
    EXPECT_EQ(status_of(write(sizeof(TestSlate) - 3, 4, 1)),
              Status_STATUS_BAD_ADDRESS);
    EXPECT_EQ(status_of(read(sizeof(TestSlate), 1)), Status_STATUS_BAD_ADDRESS);

    EXPECT_EQ(std::memcmp(&slate_, &before, sizeof(TestSlate)), 0);
}

TEST_F(SlateServerTest, LastSlotIsStillAddressable)
{
    /* The bound must not be off by one: the last 8 byte slot starts at
       size - 8 and is inside the slate. */
    EXPECT_EQ(status_of(write(sizeof(TestSlate) - 8, 8, 1)), Status_STATUS_OK);
    EXPECT_EQ(status_of(write(sizeof(TestSlate) - 1, 1, 1)), Status_STATUS_OK);
}

TEST_F(SlateServerTest, OffsetNearUint32MaxDoesNotWrap)
{
    /* offset + width would wrap to a small number and sneak past a naive
       bounds check; offset <= sizeof - width does not. */
    EXPECT_EQ(status_of(write(0xffffffff, 1, 1)), Status_STATUS_BAD_ADDRESS);
    EXPECT_EQ(status_of(write(0xfffffffc, 4, 1)), Status_STATUS_BAD_ADDRESS);
    EXPECT_EQ(status_of(write(0xfffffff8, 8, 1)), Status_STATUS_BAD_ADDRESS);
    EXPECT_EQ(status_of(read(0xffffffff, 4)), Status_STATUS_BAD_ADDRESS);
}

TEST_F(SlateServerTest, MisalignedOffsetsAreRejected)
{
    const TestSlate before = slate_;

    EXPECT_EQ(status_of(write(1, 2, 0xabcd)), Status_STATUS_BAD_ADDRESS);
    EXPECT_EQ(status_of(write(2, 4, 0xabcd)), Status_STATUS_BAD_ADDRESS);
    EXPECT_EQ(status_of(write(4, 8, 0xabcd)), Status_STATUS_BAD_ADDRESS);
    EXPECT_EQ(status_of(read(1, 4)), Status_STATUS_BAD_ADDRESS);

    EXPECT_EQ(std::memcmp(&slate_, &before, sizeof(TestSlate)), 0);
}

TEST_F(SlateServerTest, ASingleByteNeedsNoAlignment)
{
    for (uint32_t offset = 0; offset < sizeof(TestSlate); offset++) {
        EXPECT_EQ(status_of(write(offset, 1, 1)), Status_STATUS_OK)
            << "offset " << offset;
    }
}

TEST_F(SlateServerTest, FailureStillEchoesTypeOffsetAndWidth)
{
    SatMsg rsp = handle(write(2, 4, 1));

    EXPECT_EQ(rsp.type, SatMsgType_SAT_MSG_TYPE_WRITE_RESPONSE);
    EXPECT_EQ(rsp.offset, 2u);
    EXPECT_EQ(rsp.width, Width_WIDTH_4_BYTES);
}

TEST(SlateServerTinySlateTest, WidthLargerThanTheSlateIsRejected)
{
    /* sizeof(SlateT) - width underflows here unless it is guarded. */
    struct Tiny
    {
        uint8_t only;
    };
    Tiny slate{};
    SlateServer<Tiny> server{slate};

    EXPECT_EQ(server.handle(write(0, 4, 0xffffffff))->status,
              Status_STATUS_BAD_ADDRESS);
    EXPECT_EQ(server.handle(read(0, 8))->status, Status_STATUS_BAD_ADDRESS);
    EXPECT_EQ(slate.only, 0);
}

} // namespace
