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

namespace {

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

    send_cmd(usb, SatCmd{.offset = 4, .value = 1234});

    EXPECT_EQ(recv.update(), 1u);

    std::optional<SatCmd> cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->offset, 4u);
    EXPECT_EQ(cmd->value, 1234u);

    /* Only the one command was queued. */
    EXPECT_FALSE(recv.get_cmd().has_value());
}

TEST(CmdReceiverTest, DecodesBackToBackFramesInOrder)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    send_cmd(usb, SatCmd{.offset = 1, .value = 10});
    send_cmd(usb, SatCmd{.offset = 2, .value = 20});

    EXPECT_EQ(recv.update(), 2u);

    std::optional<SatCmd> first = recv.get_cmd();
    std::optional<SatCmd> second = recv.get_cmd();
    ASSERT_TRUE(first.has_value());
    ASSERT_TRUE(second.has_value());
    EXPECT_EQ(first->offset, 1u);
    EXPECT_EQ(second->offset, 2u);
}

TEST(CmdReceiverTest, WaitsForTheDelimiterAcrossUpdates)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    /* Half a frame arrives, as it would from a short usb read. */
    std::vector<uint8_t> payload = serialize(SatCmd{.offset = 7, .value = 99});
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
    EXPECT_EQ(cmd->offset, 7u);
    EXPECT_EQ(cmd->value, 99u);
}

TEST(CmdReceiverTest, RestoresZeroBytesStrippedByCobs)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    /* offset = 42, then a value of 0 spelled out as an explicit varint so
       that the payload actually carries a zero byte for cobs to strip. */
    const std::vector<uint8_t> payload = {0x08, 0x2A, 0x10, 0x00};
    send_frame(usb, payload);

    EXPECT_EQ(recv.update(), 1u);

    std::optional<SatCmd> cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->offset, 42u);
    EXPECT_EQ(cmd->value, 0u);
}

TEST(CmdReceiverTest, IgnoresStrayDelimiters)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    for (int i = 0; i < 3; i++) {
        ASSERT_TRUE(usb.push(0));
    }
    send_cmd(usb, SatCmd{.offset = 5, .value = 6});

    EXPECT_EQ(recv.update(), 1u);
    ASSERT_TRUE(recv.get_cmd().has_value());
}

TEST(CmdReceiverTest, DropsUndecodableFrameAndResyncs)
{
    UsbSim usb{};
    CmdReceiver recv{usb};

    /* Field 1 with wire type 7, which is not a thing. */
    send_frame(usb, {0x0F, 0x0F});
    send_cmd(usb, SatCmd{.offset = 8, .value = 9});

    EXPECT_EQ(recv.update(), 1u);

    std::optional<SatCmd> cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->offset, 8u);
    EXPECT_EQ(cmd->value, 9u);
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
    send_cmd(usb, SatCmd{.offset = 3, .value = 4});

    EXPECT_EQ(recv.update(), 1u);

    std::optional<SatCmd> cmd = recv.get_cmd();
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->offset, 3u);
    EXPECT_EQ(cmd->value, 4u);
}

} // namespace
