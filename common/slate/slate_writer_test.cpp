/**
 * Author: Carson Lauer
 * Date: 10 September 2026
 */
#include "common/slate/slate_writer.hpp"

#include <cstdint>
#include <cstring>

#include "gtest/gtest.h"

namespace
{

/* A stand in for the flight slate with one field of every width, laid out so
   the offsets below are stable. */
struct TestSlate
{
    uint8_t flag{};
    uint8_t mode{};
    uint16_t counter{};
    uint32_t sleep_ms{};
    float temperature{};
    bool enabled{};
    int8_t trim{};
    int16_t offset_hz{};
    int32_t drift{};
};

constexpr uint32_t kFlag = 0;
constexpr uint32_t kMode = 1;
constexpr uint32_t kCounter = 2;
constexpr uint32_t kSleepMs = 4;
constexpr uint32_t kTemperature = 8;
constexpr uint32_t kEnabled = 12;
constexpr uint32_t kTrim = 13;
constexpr uint32_t kOffsetHz = 14;
constexpr uint32_t kDrift = 16;

static_assert(offsetof(TestSlate, flag) == kFlag, "");
static_assert(offsetof(TestSlate, mode) == kMode, "");
static_assert(offsetof(TestSlate, counter) == kCounter, "");
static_assert(offsetof(TestSlate, sleep_ms) == kSleepMs, "");
static_assert(offsetof(TestSlate, temperature) == kTemperature, "");
static_assert(offsetof(TestSlate, enabled) == kEnabled, "");
static_assert(offsetof(TestSlate, trim) == kTrim, "");
static_assert(offsetof(TestSlate, offset_hz) == kOffsetHz, "");
static_assert(offsetof(TestSlate, drift) == kDrift, "");
static_assert(sizeof(TestSlate) == 20, "");

SatCmd write_u8(uint32_t offset, uint32_t value)
{
    SatCmd cmd = SatCmd_init_zero;
    cmd.which_cmd = SatCmd_write_u8_tag;
    cmd.cmd.write_u8.offset = offset;
    cmd.cmd.write_u8.value = value;
    return cmd;
}

SatCmd write_u16(uint32_t offset, uint32_t value)
{
    SatCmd cmd = SatCmd_init_zero;
    cmd.which_cmd = SatCmd_write_u16_tag;
    cmd.cmd.write_u16.offset = offset;
    cmd.cmd.write_u16.value = value;
    return cmd;
}

SatCmd write_u32(uint32_t offset, uint32_t value)
{
    SatCmd cmd = SatCmd_init_zero;
    cmd.which_cmd = SatCmd_write_u32_tag;
    cmd.cmd.write_u32.offset = offset;
    cmd.cmd.write_u32.value = value;
    return cmd;
}

SatCmd write_f32(uint32_t offset, float value)
{
    SatCmd cmd = SatCmd_init_zero;
    cmd.which_cmd = SatCmd_write_f32_tag;
    cmd.cmd.write_f32.offset = offset;
    cmd.cmd.write_f32.value = value;
    return cmd;
}

SatCmd write_signed(uint32_t offset, Width width, int32_t value)
{
    SatCmd cmd = SatCmd_init_zero;
    switch (width) {
    case Width_WIDTH_I8:
        cmd.which_cmd = SatCmd_write_i8_tag;
        cmd.cmd.write_i8.offset = offset;
        cmd.cmd.write_i8.value = value;
        break;
    case Width_WIDTH_I16:
        cmd.which_cmd = SatCmd_write_i16_tag;
        cmd.cmd.write_i16.offset = offset;
        cmd.cmd.write_i16.value = value;
        break;
    default:
        cmd.which_cmd = SatCmd_write_i32_tag;
        cmd.cmd.write_i32.offset = offset;
        cmd.cmd.write_i32.value = value;
        break;
    }
    return cmd;
}

SatCmd write_bool(uint32_t offset, bool value)
{
    SatCmd cmd = SatCmd_init_zero;
    cmd.which_cmd = SatCmd_write_bool_tag;
    cmd.cmd.write_bool.offset = offset;
    cmd.cmd.write_bool.value = value;
    return cmd;
}

SatCmd read_field(uint32_t offset, Width width)
{
    SatCmd cmd = SatCmd_init_zero;
    cmd.which_cmd = SatCmd_read_tag;
    cmd.cmd.read.offset = offset;
    cmd.cmd.read.width = width;
    return cmd;
}

uint32_t bits_of(float value)
{
    uint32_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    return bits;
}

class SlateWriterTest : public ::testing::Test
{
protected:
    TestSlate slate_{};
    SlateWriter<TestSlate> writer_{slate_};
};

TEST_F(SlateWriterTest, WriteU8Lands)
{
    SatResponse rsp = writer_.apply(write_u8(kMode, 0x42));

    EXPECT_EQ(slate_.mode, 0x42);
    EXPECT_EQ(rsp.status, Status_STATUS_OK);
    EXPECT_EQ(rsp.offset, kMode);
    EXPECT_EQ(rsp.width, Width_WIDTH_U8);
    EXPECT_EQ(rsp.which_value, SatResponse_uint_value_tag);
    EXPECT_EQ(rsp.value.uint_value, 0x42u);
}

TEST_F(SlateWriterTest, WriteU8Truncates)
{
    SatResponse rsp = writer_.apply(write_u8(kFlag, 0x1ff));

    EXPECT_EQ(slate_.flag, 0xff);
    EXPECT_EQ(slate_.mode, 0); // truncation must not spill into the neighbour
    EXPECT_EQ(rsp.value.uint_value, 0xffu); // the value that actually landed
}

TEST_F(SlateWriterTest, WriteU16Truncates)
{
    SatResponse rsp = writer_.apply(write_u16(kCounter, 0x12345));

    EXPECT_EQ(slate_.counter, 0x2345);
    EXPECT_EQ(slate_.sleep_ms, 0u);
    EXPECT_EQ(rsp.status, Status_STATUS_OK);
    EXPECT_EQ(rsp.width, Width_WIDTH_U16);
    EXPECT_EQ(rsp.value.uint_value, 0x2345u);
}

TEST_F(SlateWriterTest, WriteU32KeepsEveryBit)
{
    SatResponse rsp = writer_.apply(write_u32(kSleepMs, 0xdeadbeef));

    EXPECT_EQ(slate_.sleep_ms, 0xdeadbeefu);
    EXPECT_EQ(rsp.status, Status_STATUS_OK);
    EXPECT_EQ(rsp.value.uint_value, 0xdeadbeefu);
}

TEST_F(SlateWriterTest, WriteF32IsBitExact)
{
    const float value = 3.14159274f;
    SatResponse rsp = writer_.apply(write_f32(kTemperature, value));

    EXPECT_EQ(bits_of(slate_.temperature), bits_of(value));
    EXPECT_EQ(rsp.status, Status_STATUS_OK);
    EXPECT_EQ(rsp.width, Width_WIDTH_F32);
    EXPECT_EQ(rsp.which_value, SatResponse_float_value_tag);
    EXPECT_EQ(bits_of(rsp.value.float_value), bits_of(value));
}

TEST_F(SlateWriterTest, WriteF32KeepsNegativeZeroSign)
{
    SatResponse rsp = writer_.apply(write_f32(kTemperature, -0.0f));

    EXPECT_EQ(bits_of(slate_.temperature), 0x80000000u);
    EXPECT_EQ(bits_of(rsp.value.float_value), 0x80000000u);
}

TEST_F(SlateWriterTest, ReadReturnsCurrentValues)
{
    slate_.flag = 7;
    slate_.counter = 0x0102;
    slate_.sleep_ms = 250;
    slate_.temperature = -12.5f;

    EXPECT_EQ(writer_.apply(read_field(kFlag, Width_WIDTH_U8)).value.uint_value,
              7u);
    EXPECT_EQ(
        writer_.apply(read_field(kCounter, Width_WIDTH_U16)).value.uint_value,
        0x0102u);
    EXPECT_EQ(
        writer_.apply(read_field(kSleepMs, Width_WIDTH_U32)).value.uint_value,
        250u);

    SatResponse rsp = writer_.apply(read_field(kTemperature, Width_WIDTH_F32));
    EXPECT_EQ(rsp.which_value, SatResponse_float_value_tag);
    EXPECT_EQ(bits_of(rsp.value.float_value), bits_of(-12.5f));
}

TEST_F(SlateWriterTest, ReadLeavesTheSlateAlone)
{
    slate_.sleep_ms = 500;
    SatResponse rsp = writer_.apply(read_field(kSleepMs, Width_WIDTH_U32));

    EXPECT_EQ(rsp.status, Status_STATUS_OK);
    EXPECT_EQ(slate_.sleep_ms, 500u);
}

TEST_F(SlateWriterTest, WriteThenReadRoundTrips)
{
    writer_.apply(write_u32(kSleepMs, 1000));
    writer_.apply(write_f32(kTemperature, 21.5f));

    EXPECT_EQ(
        writer_.apply(read_field(kSleepMs, Width_WIDTH_U32)).value.uint_value,
        1000u);
    EXPECT_EQ(bits_of(writer_.apply(read_field(kTemperature, Width_WIDTH_F32))
                          .value.float_value),
              bits_of(21.5f));
}

TEST_F(SlateWriterTest, ReadOfUnspecifiedWidthIsBadCommand)
{
    SatResponse rsp = writer_.apply(read_field(kFlag, Width_WIDTH_UNSPECIFIED));

    EXPECT_EQ(rsp.status, Status_STATUS_BAD_COMMAND);
    EXPECT_EQ(rsp.offset, kFlag);
}

TEST_F(SlateWriterTest, UnsetVariantIsBadCommand)
{
    SatCmd cmd = SatCmd_init_zero; // which_cmd == 0, no variant selected
    SatResponse rsp = writer_.apply(cmd);

    EXPECT_EQ(rsp.status, Status_STATUS_BAD_COMMAND);
    EXPECT_EQ(rsp.width, Width_WIDTH_UNSPECIFIED);
}

TEST_F(SlateWriterTest, OffsetPastTheEndIsRejected)
{
    const TestSlate before = slate_;

    /* One past the last byte, and the last byte of a u32 hanging off the end.
     */
    EXPECT_EQ(writer_.apply(write_u8(sizeof(TestSlate), 1)).status,
              Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(writer_.apply(write_u32(sizeof(TestSlate) - 3, 1)).status,
              Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(
        writer_.apply(read_field(sizeof(TestSlate), Width_WIDTH_U8)).status,
        Status_STATUS_BAD_OFFSET);

    EXPECT_EQ(std::memcmp(&slate_, &before, sizeof(TestSlate)), 0);
}

TEST_F(SlateWriterTest, LastFieldIsStillAddressable)
{
    /* The bound must not be off by one: the last u32 sized slot starts at
       size - 4 and is inside the slate. Which field lives there depends on
       the layout, so check the write lands rather than naming one. */
    SatResponse rsp =
        writer_.apply(write_u32(sizeof(TestSlate) - 4, 0xa5a5a5a5));

    EXPECT_EQ(rsp.status, Status_STATUS_OK);
    EXPECT_EQ(writer_.apply(write_u32(kTemperature, 0xa5a5a5a5)).status,
              Status_STATUS_OK);
    EXPECT_EQ(bits_of(slate_.temperature), 0xa5a5a5a5u);
}

TEST_F(SlateWriterTest, OffsetNearUint32MaxDoesNotWrap)
{
    /* offset + width would wrap to a small number and sneak past a naive
       bounds check; offset <= sizeof - width does not. */
    EXPECT_EQ(writer_.apply(write_u32(0xffffffff, 1)).status,
              Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(writer_.apply(write_u8(0xffffffff, 1)).status,
              Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(writer_.apply(write_f32(0xfffffffc, 1.0f)).status,
              Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(writer_.apply(read_field(0xffffffff, Width_WIDTH_U32)).status,
              Status_STATUS_BAD_OFFSET);
}

TEST_F(SlateWriterTest, MisalignedOffsetsAreRejected)
{
    const TestSlate before = slate_;

    EXPECT_EQ(writer_.apply(write_u16(1, 0xabcd)).status,
              Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(writer_.apply(write_u32(2, 0xabcd)).status,
              Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(writer_.apply(write_f32(kTemperature + 1, 1.0f)).status,
              Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(writer_.apply(read_field(1, Width_WIDTH_U32)).status,
              Status_STATUS_BAD_OFFSET);

    EXPECT_EQ(std::memcmp(&slate_, &before, sizeof(TestSlate)), 0);
}

TEST_F(SlateWriterTest, FailureStillEchoesOffsetAndWidth)
{
    SatResponse rsp = writer_.apply(write_u32(2, 1));

    EXPECT_EQ(rsp.offset, 2u);
    EXPECT_EQ(rsp.width, Width_WIDTH_U32);
}

TEST(SlateWriterTinySlateTest, WidthLargerThanTheSlateIsRejected)
{
    /* sizeof(SlateT) - width underflows here unless it is guarded. */
    struct Tiny
    {
        uint8_t only;
    };
    Tiny slate{};
    SlateWriter<Tiny> writer{slate};

    EXPECT_EQ(writer.apply(write_u32(0, 0xffffffff)).status,
              Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(writer.apply(read_field(0, Width_WIDTH_F32)).status,
              Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(slate.only, 0);
}

TEST_F(SlateWriterTest, WritesABool)
{
    SatResponse rsp = writer_.apply(write_bool(kEnabled, true));

    EXPECT_EQ(rsp.status, Status_STATUS_OK);
    EXPECT_EQ(rsp.offset, kEnabled);
    EXPECT_EQ(rsp.width, Width_WIDTH_BOOL);
    EXPECT_EQ(rsp.which_value, SatResponse_bool_value_tag);
    EXPECT_TRUE(rsp.value.bool_value);
    EXPECT_TRUE(slate_.enabled);
}

TEST_F(SlateWriterTest, ClearsABool)
{
    slate_.enabled = true;

    SatResponse rsp = writer_.apply(write_bool(kEnabled, false));

    EXPECT_EQ(rsp.status, Status_STATUS_OK);
    EXPECT_EQ(rsp.which_value, SatResponse_bool_value_tag);
    EXPECT_FALSE(rsp.value.bool_value);
    EXPECT_FALSE(slate_.enabled);
}

TEST_F(SlateWriterTest, ABoolIsStoredAsExactlyOneByte)
{
    /* The neighbouring bytes are padding here, but the same offset in a
       real slate could be a field, so a bool write must not spill. */
    writer_.apply(write_u8(kEnabled + 1, 0xAB));
    writer_.apply(write_bool(kEnabled, true));

    EXPECT_EQ(reinterpret_cast<uint8_t *>(&slate_)[kEnabled], 1);
    EXPECT_EQ(reinterpret_cast<uint8_t *>(&slate_)[kEnabled + 1], 0xAB);
}

TEST_F(SlateWriterTest, AWrittenBoolIsNormalisedToZeroOrOne)
{
    /* A bool whose byte is neither 0 nor 1 is not a valid bool, so the
       write stores 1 rather than whatever the ground happened to send. */
    writer_.apply(write_bool(kEnabled, true));

    EXPECT_EQ(reinterpret_cast<uint8_t *>(&slate_)[kEnabled], 1);
}

TEST_F(SlateWriterTest, ReadsAnyNonZeroByteAsTrue)
{
    /* Another field's write could leave 0x02 at a bool's offset. Reading
       that as a bool must not be undefined, and must say true. */
    writer_.apply(write_u8(kEnabled, 0x02));

    SatResponse rsp = writer_.apply(read_field(kEnabled, Width_WIDTH_BOOL));

    EXPECT_EQ(rsp.status, Status_STATUS_OK);
    EXPECT_EQ(rsp.which_value, SatResponse_bool_value_tag);
    EXPECT_TRUE(rsp.value.bool_value);
}

TEST_F(SlateWriterTest, RefusesABoolPastTheEnd)
{
    SatResponse rsp = writer_.apply(write_bool(sizeof(TestSlate), true));

    EXPECT_EQ(rsp.status, Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(rsp.width, Width_WIDTH_BOOL);
}

TEST_F(SlateWriterTest, ABoolNeedsNoAlignment)
{
    /* One byte wide, so every offset inside the slate is fair game. */
    for (uint32_t offset = 0; offset < sizeof(TestSlate); offset++) {
        EXPECT_EQ(writer_.apply(write_bool(offset, true)).status,
                  Status_STATUS_OK)
            << "offset " << offset;
    }
}

TEST_F(SlateWriterTest, WritesANegativeI32)
{
    SatResponse rsp = writer_.apply(write_signed(kDrift, Width_WIDTH_I32, -5));

    EXPECT_EQ(rsp.status, Status_STATUS_OK);
    EXPECT_EQ(rsp.width, Width_WIDTH_I32);
    EXPECT_EQ(rsp.which_value, SatResponse_int_value_tag);
    EXPECT_EQ(rsp.value.int_value, -5);
    EXPECT_EQ(slate_.drift, -5);
}

TEST_F(SlateWriterTest, WritesNegativeI8AndI16)
{
    EXPECT_EQ(writer_.apply(write_signed(kTrim, Width_WIDTH_I8, -1)).status,
              Status_STATUS_OK);
    EXPECT_EQ(slate_.trim, -1);

    EXPECT_EQ(
        writer_.apply(write_signed(kOffsetHz, Width_WIDTH_I16, -300)).status,
        Status_STATUS_OK);
    EXPECT_EQ(slate_.offset_hz, -300);
}

TEST_F(SlateWriterTest, SignedExtremesSurvive)
{
    writer_.apply(write_signed(kTrim, Width_WIDTH_I8, -128));
    EXPECT_EQ(slate_.trim, -128);
    writer_.apply(write_signed(kTrim, Width_WIDTH_I8, 127));
    EXPECT_EQ(slate_.trim, 127);

    writer_.apply(write_signed(kDrift, Width_WIDTH_I32, INT32_MIN));
    EXPECT_EQ(slate_.drift, INT32_MIN);
    writer_.apply(write_signed(kDrift, Width_WIDTH_I32, INT32_MAX));
    EXPECT_EQ(slate_.drift, INT32_MAX);
}

TEST_F(SlateWriterTest, ASignedWriteNarrowsModularly)
{
    /* 200 does not fit in an int8; c++20 says the cast wraps, so it lands
       as -56 and the reply says so rather than claiming 200. */
    SatResponse rsp = writer_.apply(write_signed(kTrim, Width_WIDTH_I8, 200));

    EXPECT_EQ(rsp.value.int_value, -56);
    EXPECT_EQ(slate_.trim, -56);
}

TEST_F(SlateWriterTest, SignedAndUnsignedSeeTheSameBytes)
{
    /* The flight side knows offsets, not field types: the same four bytes
       read back either way, which is what lets the ground decide. */
    writer_.apply(write_signed(kDrift, Width_WIDTH_I32, -1));

    SatResponse as_uint = writer_.apply(read_field(kDrift, Width_WIDTH_U32));
    EXPECT_EQ(as_uint.which_value, SatResponse_uint_value_tag);
    EXPECT_EQ(as_uint.value.uint_value, 0xFFFFFFFFu);

    SatResponse as_int = writer_.apply(read_field(kDrift, Width_WIDTH_I32));
    EXPECT_EQ(as_int.which_value, SatResponse_int_value_tag);
    EXPECT_EQ(as_int.value.int_value, -1);
}

TEST_F(SlateWriterTest, SignedWritesAreStillBoundsAndAlignmentChecked)
{
    EXPECT_EQ(writer_.apply(write_signed(sizeof(TestSlate), Width_WIDTH_I32, 1))
                  .status,
              Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(
        writer_.apply(write_signed(kDrift + 1, Width_WIDTH_I32, 1)).status,
        Status_STATUS_BAD_OFFSET);
    EXPECT_EQ(
        writer_.apply(write_signed(0xFFFFFFFF, Width_WIDTH_I32, 1)).status,
        Status_STATUS_BAD_OFFSET);
}

} // namespace
