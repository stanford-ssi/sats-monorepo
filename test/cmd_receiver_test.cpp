/**
 * Unit tests for CmdReceiver.
 *
 * A RingBuffer stands in for the usb rx queue, so each test can push exactly
 * the bytes a ground station would send: cobs encoded nanopb frames, each
 * followed by a zero delimiter.
 */
#include <gtest/gtest.h>

#include <cstdint>
#include <vector>

#include "pb_encode.h"
#include "proto/sats_command.pb.h"

#include "common/cmd_receiver/cmd_receiver.hpp"
#include "common/cobs/cobs.hpp"
#include "common/util/ring_buffer.hpp"

namespace
{

using UsbSim = RingBuffer<uint8_t, 1024>;

/* Cobs encode `payload` and push it, plus its delimiter, onto the link. */
void send_frame(UsbSim &usb, const std::vector<uint8_t> &payload)
{
    std::vector<uint8_t> encoded(payload.size() + payload.size() / 254 + 2);
    uint32_t n = cobs_encode(payload.data(), payload.size(), encoded.data());

    for (uint32_t i = 0; i < n; i++) {
        ASSERT_NE(encoded[i], 0); // cobs guarantees this, and we rely on it
        ASSERT_TRUE(usb.push(encoded[i]));
    }
    ASSERT_TRUE(usb.push(0));
}

/* The bytes a SatCmd goes out as on the wire, before cobs encoding. */
std::vector<uint8_t> serialize(const SatCmd &cmd)
{
    std::vector<uint8_t> out(SatCmd_size);
    pb_ostream_t stream = pb_ostream_from_buffer(out.data(), out.size());
    EXPECT_TRUE(pb_encode(&stream, &SatCmd_msg, &cmd));
    out.resize(stream.bytes_written);
    return out;
}

void send_cmd(UsbSim &usb, const SatCmd &cmd)
{
    send_frame(usb, serialize(cmd));
}

SatCmd write_u8(uint32_t offset, uint32_t value)
{
    SatCmd cmd = SatCmd_init_zero;
    cmd.which_cmd = SatCmd_write_u8_tag;
    cmd.cmd.write_u8 = {offset, value};
    return cmd;
}

SatCmd write_u16(uint32_t offset, uint32_t value)
{
    SatCmd cmd = SatCmd_init_zero;
    cmd.which_cmd = SatCmd_write_u16_tag;
    cmd.cmd.write_u16 = {offset, value};
    return cmd;
}

SatCmd write_u32(uint32_t offset, uint32_t value)
{
    SatCmd cmd = SatCmd_init_zero;
    cmd.which_cmd = SatCmd_write_u32_tag;
    cmd.cmd.write_u32 = {offset, value};
    return cmd;
}

SatCmd write_f32(uint32_t offset, float value)
{
    SatCmd cmd = SatCmd_init_zero;
    cmd.which_cmd = SatCmd_write_f32_tag;
    cmd.cmd.write_f32 = {offset, value};
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
    cmd.cmd.read = {offset, width};
    return cmd;
}

TEST(CmdReceiverTest, NothingOnTheLinkYieldsNothing)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    EXPECT_EQ(recv.update(), 0u);
    EXPECT_FALSE(recv.get_cmd().has_value());
}

TEST(CmdReceiverTest, DecodesOneCommand)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    send_cmd(usb, write_u8(4, 123));

    EXPECT_EQ(recv.update(), 1u);

    std::optional<SatCmd> cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->which_cmd, SatCmd_write_u8_tag);
    EXPECT_EQ(cmd->cmd.write_u8.offset, 4u);
    EXPECT_EQ(cmd->cmd.write_u8.value, 123u);

    /* Only the one command was queued. */
    EXPECT_FALSE(recv.get_cmd().has_value());
}

TEST(CmdReceiverTest, DecodesEveryVariant)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    send_cmd(usb, write_u8(4, 0xFF));
    send_cmd(usb, write_u16(8, 0xBEEF));
    send_cmd(usb, write_u32(12, 0xDEADBEEF));
    send_cmd(usb, write_f32(16, -2.5f));
    send_cmd(usb, write_bool(20, true));
    send_cmd(usb, read_field(24, Width_WIDTH_F32));

    EXPECT_EQ(recv.update(), 6u);

    std::optional<SatCmd> cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->which_cmd, SatCmd_write_u8_tag);
    EXPECT_EQ(cmd->cmd.write_u8.offset, 4u);
    EXPECT_EQ(cmd->cmd.write_u8.value, 0xFFu);

    cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->which_cmd, SatCmd_write_u16_tag);
    EXPECT_EQ(cmd->cmd.write_u16.offset, 8u);
    EXPECT_EQ(cmd->cmd.write_u16.value, 0xBEEFu);

    cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->which_cmd, SatCmd_write_u32_tag);
    EXPECT_EQ(cmd->cmd.write_u32.offset, 12u);
    EXPECT_EQ(cmd->cmd.write_u32.value, 0xDEADBEEFu);

    cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->which_cmd, SatCmd_write_f32_tag);
    EXPECT_EQ(cmd->cmd.write_f32.offset, 16u);
    EXPECT_EQ(cmd->cmd.write_f32.value, -2.5f);

    cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->which_cmd, SatCmd_write_bool_tag);
    EXPECT_EQ(cmd->cmd.write_bool.offset, 20u);
    EXPECT_TRUE(cmd->cmd.write_bool.value);

    cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->which_cmd, SatCmd_read_tag);
    EXPECT_EQ(cmd->cmd.read.offset, 24u);
    EXPECT_EQ(cmd->cmd.read.width, Width_WIDTH_F32);
}

TEST(CmdReceiverTest, DecodesBackToBackFramesInOrder)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    send_cmd(usb, write_u8(1, 10));
    send_cmd(usb, write_u8(2, 20));

    EXPECT_EQ(recv.update(), 2u);

    std::optional<SatCmd> first = recv.get_cmd();
    std::optional<SatCmd> second = recv.get_cmd();
    ASSERT_TRUE(first.has_value());
    ASSERT_TRUE(second.has_value());
    EXPECT_EQ(first->cmd.write_u8.offset, 1u);
    EXPECT_EQ(second->cmd.write_u8.offset, 2u);
}

TEST(CmdReceiverTest, WaitsForTheDelimiterAcrossUpdates)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    /* Half a frame arrives, as it would from a short usb read. */
    std::vector<uint8_t> payload = serialize(write_u16(7, 99));
    std::vector<uint8_t> encoded(payload.size() + 2);
    uint32_t n = cobs_encode(payload.data(), payload.size(), encoded.data());
    ASSERT_GT(n, 1u);

    for (uint32_t i = 0; i < n - 1; i++) {
        ASSERT_TRUE(usb.push(encoded[i]));
    }
    EXPECT_EQ(recv.update(), 0u);
    EXPECT_FALSE(recv.get_cmd().has_value());

    /* The rest shows up on a later poll. */
    ASSERT_TRUE(usb.push(encoded[n - 1]));
    ASSERT_TRUE(usb.push(0));
    EXPECT_EQ(recv.update(), 1u);

    std::optional<SatCmd> cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->which_cmd, SatCmd_write_u16_tag);
    EXPECT_EQ(cmd->cmd.write_u16.offset, 7u);
    EXPECT_EQ(cmd->cmd.write_u16.value, 99u);
}

TEST(CmdReceiverTest, RestoresZeroBytesStrippedByCobs)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    /* write_u8{offset = 42, value = 0}, with the zero value spelled out as
       an explicit varint rather than omitted the way proto3 would, so that
       the payload actually carries a zero byte for cobs to strip. */
    const std::vector<uint8_t> payload = {0x0A, 0x04, 0x08, 0x2A, 0x10, 0x00};
    send_frame(usb, payload);

    EXPECT_EQ(recv.update(), 1u);

    std::optional<SatCmd> cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->which_cmd, SatCmd_write_u8_tag);
    EXPECT_EQ(cmd->cmd.write_u8.offset, 42u);
    EXPECT_EQ(cmd->cmd.write_u8.value, 0u);
}

TEST(CmdReceiverTest, RestoresTheZeroBytesInsideAFloat)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    /* 1.0f is 00 00 80 3f on the wire, so two thirds of its bytes are zeros
       cobs has to stand in for. No hand written payload needed. */
    send_cmd(usb, write_f32(64, 1.0f));

    EXPECT_EQ(recv.update(), 1u);

    std::optional<SatCmd> cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->which_cmd, SatCmd_write_f32_tag);
    EXPECT_EQ(cmd->cmd.write_f32.offset, 64u);
    EXPECT_EQ(cmd->cmd.write_f32.value, 1.0f);
}

TEST(CmdReceiverTest, IgnoresStrayDelimiters)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    for (int i = 0; i < 3; i++) {
        ASSERT_TRUE(usb.push(0));
    }
    send_cmd(usb, write_u8(5, 6));

    EXPECT_EQ(recv.update(), 1u);
    ASSERT_TRUE(recv.get_cmd().has_value());
}

TEST(CmdReceiverTest, DropsUndecodableFrameAndResyncs)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    /* Field 1 with wire type 7, which is not a thing. */
    send_frame(usb, {0x0F, 0x0F});
    send_cmd(usb, write_u32(8, 9));

    EXPECT_EQ(recv.update(), 1u);

    std::optional<SatCmd> cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->which_cmd, SatCmd_write_u32_tag);
    EXPECT_EQ(cmd->cmd.write_u32.offset, 8u);
    EXPECT_EQ(cmd->cmd.write_u32.value, 9u);
}

TEST(CmdReceiverTest, DropsOversizedFrameAndResyncs)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    /* Longer than the reassembly buffer, and with the first zero far enough
       in that cobs has to emit a full 254 byte block to cover it. */
    std::vector<uint8_t> huge(300, 0xAB);
    huge[280] = 0;
    send_frame(usb, huge);
    send_cmd(usb, write_u8(3, 4));

    EXPECT_EQ(recv.update(), 1u);

    std::optional<SatCmd> cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->which_cmd, SatCmd_write_u8_tag);
    EXPECT_EQ(cmd->cmd.write_u8.offset, 3u);
    EXPECT_EQ(cmd->cmd.write_u8.value, 4u);
}

} // namespace
