/**
 * Unit tests for SatLink.
 *
 * Ring buffers stand in for the usb queues, so each test can push exactly
 * the bytes the far end would send, cobs encoded nanopb frames each followed
 * by a zero delimiter, and inspect exactly the bytes that go out.
 */
#include <gtest/gtest.h>

#include <cstdint>
#include <cstring>
#include <vector>

#include "pb_encode.h"
#include "proto/sats_command.pb.h"

#include "common/cobs/cobs.hpp"
#include "common/sat_link/sat_link.hpp"
#include "common/util/ring_buffer.hpp"

namespace
{

using UsbSim = RingBuffer<uint8_t, 1024>;
using Link = SatLink<SatMsg, SatMsg>;

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

/* The bytes a SatMsg goes out as on the wire, before cobs encoding. */
std::vector<uint8_t> serialize(const SatMsg &msg)
{
    std::vector<uint8_t> out(SatMsg_size);
    pb_ostream_t stream = pb_ostream_from_buffer(out.data(), out.size());
    EXPECT_TRUE(pb_encode(&stream, &SatMsg_msg, &msg));
    out.resize(stream.bytes_written);
    return out;
}

void send_msg(UsbSim &usb, const SatMsg &msg)
{
    send_frame(usb, serialize(msg));
}

SatMsg make(SatMsgType type, uint32_t offset, uint32_t width,
            uint32_t value = 0, Status status = Status_STATUS_OK)
{
    SatMsg msg = SatMsg_init_zero;
    msg.type = type;
    msg.offset = offset;
    msg.width = static_cast<Width>(width); // any value, valid or not
    msg.value = value;
    msg.status = status;
    return msg;
}

uint32_t bits_of(float value)
{
    uint32_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    return bits;
}

void expect_same(const SatMsg &got, const SatMsg &want)
{
    EXPECT_EQ(got.type, want.type);
    EXPECT_EQ(got.offset, want.offset);
    EXPECT_EQ(got.width, want.width);
    EXPECT_EQ(got.value, want.value);
    EXPECT_EQ(got.status, want.status);
}

class SatLinkTest : public ::testing::Test
{
protected:
    UsbSim in_{};
    UsbSim out_{};
    Link link_{in_, out_};
};

/* -- receiving ----------------------------------------------------------- */

TEST_F(SatLinkTest, NothingOnTheLinkYieldsNothing)
{
    EXPECT_EQ(link_.update(), 0u);
    EXPECT_FALSE(link_.receive().has_value());
}

TEST_F(SatLinkTest, DecodesOneMessage)
{
    send_msg(in_, make(SatMsgType_SAT_MSG_TYPE_WRITE, 4, 1, 123));

    EXPECT_EQ(link_.update(), 1u);

    std::optional<SatMsg> msg = link_.receive();
    ASSERT_TRUE(msg.has_value());
    expect_same(*msg, make(SatMsgType_SAT_MSG_TYPE_WRITE, 4, 1, 123));

    /* Only the one message was queued. */
    EXPECT_FALSE(link_.receive().has_value());
}

TEST_F(SatLinkTest, DecodesEveryType)
{
    /* Symmetric: requests and responses both arrive on the same link. */
    const SatMsg sent[] = {
        make(SatMsgType_SAT_MSG_TYPE_READ, 8, 4),
        make(SatMsgType_SAT_MSG_TYPE_WRITE, 12, 4, 0xDEADBEEF),
        make(SatMsgType_SAT_MSG_TYPE_READ_RESPONSE, 16, 2, 0xBEEF),
        make(SatMsgType_SAT_MSG_TYPE_WRITE_RESPONSE, 20, 4, 0,
             Status_STATUS_BAD_ADDRESS),
    };
    for (const SatMsg &msg : sent) {
        send_msg(in_, msg);
    }

    EXPECT_EQ(link_.update(), 4u);
    for (const SatMsg &want : sent) {
        std::optional<SatMsg> got = link_.receive();
        ASSERT_TRUE(got.has_value());
        expect_same(*got, want);
    }
}

TEST_F(SatLinkTest, CarriesAll32BitsOfValue)
{
    send_msg(in_, make(SatMsgType_SAT_MSG_TYPE_WRITE, 0, 4, 0xFEDCBA98));

    ASSERT_EQ(link_.update(), 1u);
    EXPECT_EQ(link_.receive()->value, 0xFEDCBA98u);
}

TEST_F(SatLinkTest, WaitsForTheDelimiterAcrossUpdates)
{
    /* Half a frame arrives, as it would from a short usb read. */
    std::vector<uint8_t> payload =
        serialize(make(SatMsgType_SAT_MSG_TYPE_WRITE, 6, 2, 99));
    std::vector<uint8_t> encoded(payload.size() + 2);
    uint32_t n = cobs_encode(payload.data(), payload.size(), encoded.data());
    ASSERT_GT(n, 1u);

    for (uint32_t i = 0; i < n - 1; i++) {
        ASSERT_TRUE(in_.push(encoded[i]));
    }
    EXPECT_EQ(link_.update(), 0u);
    EXPECT_FALSE(link_.receive().has_value());

    /* The rest shows up on a later poll. */
    ASSERT_TRUE(in_.push(encoded[n - 1]));
    ASSERT_TRUE(in_.push(0));
    EXPECT_EQ(link_.update(), 1u);

    std::optional<SatMsg> msg = link_.receive();
    ASSERT_TRUE(msg.has_value());
    expect_same(*msg, make(SatMsgType_SAT_MSG_TYPE_WRITE, 6, 2, 99));
}

TEST_F(SatLinkTest, RestoresTheZeroBytesInsideAValue)
{
    /* 1.0f is 00 00 80 3f in memory, and a varint of it still carries zero
       bytes in the payload around it for cobs to stand in for. */
    send_msg(in_, make(SatMsgType_SAT_MSG_TYPE_WRITE, 64, 4, bits_of(1.0f)));

    ASSERT_EQ(link_.update(), 1u);
    EXPECT_EQ(link_.receive()->value, bits_of(1.0f));
}

TEST_F(SatLinkTest, RestoresAnExplicitZeroField)
{
    /* type = WRITE, width = 1, offset = 42, value = 0, with the zero value
       spelled out as an explicit varint rather than omitted the way proto3
       would, so that the payload actually carries a zero byte for cobs. */
    send_frame(in_, {0x08, 0x02, 0x10, 0x01, 0x20, 0x2A, 0x28, 0x00});

    ASSERT_EQ(link_.update(), 1u);
    expect_same(*link_.receive(),
                make(SatMsgType_SAT_MSG_TYPE_WRITE, 42, 1, 0));
}

TEST_F(SatLinkTest, IgnoresStrayDelimiters)
{
    for (int i = 0; i < 3; i++) {
        ASSERT_TRUE(in_.push(0));
    }
    send_msg(in_, make(SatMsgType_SAT_MSG_TYPE_READ, 5, 1));

    EXPECT_EQ(link_.update(), 1u);
    ASSERT_TRUE(link_.receive().has_value());
}

TEST_F(SatLinkTest, DropsUndecodableFrameAndResyncs)
{
    /* Field 1 with wire type 7, which is not a thing. */
    send_frame(in_, {0x0F, 0x0F});
    send_msg(in_, make(SatMsgType_SAT_MSG_TYPE_WRITE, 8, 4, 9));

    EXPECT_EQ(link_.update(), 1u);
    expect_same(*link_.receive(), make(SatMsgType_SAT_MSG_TYPE_WRITE, 8, 4, 9));
}

TEST_F(SatLinkTest, DropsAWidthThatDoesNotFitInAByte)
{
    /* width = 260, which a one byte field would truncate to 4: a valid
       width, at an offset the sender never meant. nanopb must refuse the
       frame outright instead. */
    send_frame(in_, {0x08, 0x01, 0x10, 0x84, 0x02, 0x20, 0x00});
    send_msg(in_, make(SatMsgType_SAT_MSG_TYPE_READ, 4, 4));

    EXPECT_EQ(link_.update(), 1u);
    expect_same(*link_.receive(), make(SatMsgType_SAT_MSG_TYPE_READ, 4, 4));
}

TEST_F(SatLinkTest, DropsOversizedFrameAndResyncs)
{
    /* Longer than the reassembly buffer, and with the first zero far enough
       in that cobs has to emit a full 254 byte block to cover it. */
    std::vector<uint8_t> huge(300, 0xAB);
    huge[280] = 0;
    send_frame(in_, huge);
    send_msg(in_, make(SatMsgType_SAT_MSG_TYPE_WRITE, 3, 1, 4));

    EXPECT_EQ(link_.update(), 1u);
    expect_same(*link_.receive(), make(SatMsgType_SAT_MSG_TYPE_WRITE, 3, 1, 4));
}

/* -- sending ------------------------------------------------------------- */

TEST_F(SatLinkTest, FramesAreDelimitedAndFreeOfZeros)
{
    ASSERT_TRUE(
        link_.send(make(SatMsgType_SAT_MSG_TYPE_READ_RESPONSE, 1, 2, 0)));

    std::vector<uint8_t> wire;
    uint8_t c{};
    while (out_.pop(c)) {
        wire.push_back(c);
    }

    ASSERT_FALSE(wire.empty());
    EXPECT_EQ(wire.back(), 0); // the delimiter, and the only zero
    for (std::size_t i = 0; i + 1 < wire.size(); i++) {
        EXPECT_NE(wire[i], 0);
    }
}

TEST_F(SatLinkTest, RefusesAMessageThatWouldEncodeToNothing)
{
    /* Every field at its default, type included, serializes to zero bytes:
       a frame the far end would throw away as a stray delimiter. */
    EXPECT_FALSE(link_.send(SatMsg_init_zero));
    EXPECT_TRUE(out_.empty());
}

TEST_F(SatLinkTest, ReportsAFullQueueAndCleansUpTheTornFrame)
{
    /* Only room for one of these frames plus change, so the second send
       runs out of space partway through and leaves a fragment behind. */
    RingBuffer<uint8_t, 16> tiny{};
    Link link{in_, tiny};

    const SatMsg rsp = make(SatMsgType_SAT_MSG_TYPE_READ_RESPONSE, 8, 4, 42);
    ASSERT_TRUE(link.send(rsp));
    EXPECT_FALSE(link.send(rsp));

    /* The far end reads the link dry, fragment and all. */
    uint8_t c{};
    while (tiny.pop(c)) {
    }

    /* The next send closes the fragment off with a delimiter of its own
       before writing its frame, so the frame arrives intact. */
    ASSERT_TRUE(link.send(rsp));
    ASSERT_TRUE(tiny.pop(c));
    EXPECT_EQ(c, 0);

    Link far{tiny, out_};
    ASSERT_EQ(far.update(), 1u);
    expect_same(*far.receive(), rsp);
}

/* -- both ends ----------------------------------------------------------- */

TEST(SatLinkPairTest, TwoLinksTalkToEachOther)
{
    /* Two microcontrollers on one line: each one's out is the other's in.
       Either can ask, and either can answer. */
    UsbSim a_to_b{};
    UsbSim b_to_a{};
    Link a{b_to_a, a_to_b};
    Link b{a_to_b, b_to_a};

    ASSERT_TRUE(a.send(make(SatMsgType_SAT_MSG_TYPE_READ, 4, 4)));
    ASSERT_TRUE(b.send(make(SatMsgType_SAT_MSG_TYPE_WRITE, 0, 1, 7)));

    ASSERT_EQ(b.update(), 1u);
    expect_same(*b.receive(), make(SatMsgType_SAT_MSG_TYPE_READ, 4, 4));
    ASSERT_TRUE(
        b.send(make(SatMsgType_SAT_MSG_TYPE_READ_RESPONSE, 4, 4, 1234)));

    ASSERT_EQ(a.update(), 2u);
    expect_same(*a.receive(), make(SatMsgType_SAT_MSG_TYPE_WRITE, 0, 1, 7));
    expect_same(*a.receive(),
                make(SatMsgType_SAT_MSG_TYPE_READ_RESPONSE, 4, 4, 1234));
}

} // namespace
