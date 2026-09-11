/**
 * Unit tests for CmdResponder.
 *
 * A RingBuffer stands in for the usb tx queue. Most tests are round trips:
 * send a SatResponse, then pull the exact bytes back off the queue and
 * decode them the way the ground station will, and the two must match.
 */
#include <gtest/gtest.h>

#include <cstdint>
#include <optional>
#include <vector>

#include "pb_decode.h"
#include "proto/sats_command.pb.h"

#include "common/cmd_responder/cmd_responder.hpp"
#include "common/cobs/cobs.hpp"
#include "common/util/ring_buffer.hpp"

namespace {

using UsbSim = RingBuffer<uint8_t, 1024>;

/* Pull one frame off the link and decode it the way the ground will: gather
   bytes up to the delimiter, undo the cobs framing, hand it to nanopb.
   Frames that carry no payload are skipped exactly as CmdReceiver skips
   them, since an idle link is all delimiters. */
std::optional<SatResponse> recv_response(Queue<uint8_t> &link)
{
    std::vector<uint8_t> frame;
    uint8_t c{};
    while (link.pop(c)) {
        if (c != 0) {
            frame.push_back(c);
            continue;
        }

        std::vector<uint8_t> payload(frame.size());
        uint32_t n = cobs_decode(frame.data(), frame.size(), payload.data());
        frame.clear();
        if (n == 0) {
            continue;
        }

        SatResponse rsp = SatResponse_init_zero;
        pb_istream_t stream = pb_istream_from_buffer(payload.data(), n);
        if (!pb_decode(&stream, &SatResponse_msg, &rsp)) {
            return {};
        }
        return rsp;
    }
    return {};
}

void expect_round_trip(const SatResponse &sent)
{
    UsbSim usb{};
    CmdResponder responder{usb};

    ASSERT_TRUE(responder.send(sent));

    std::optional<SatResponse> got = recv_response(usb);
    ASSERT_TRUE(got.has_value());
    EXPECT_EQ(got->status, sent.status);
    EXPECT_EQ(got->offset, sent.offset);
    EXPECT_EQ(got->width, sent.width);
    EXPECT_EQ(got->which_value, sent.which_value);
    if (sent.which_value == SatResponse_uint_value_tag) {
        EXPECT_EQ(got->value.uint_value, sent.value.uint_value);
    } else if (sent.which_value == SatResponse_float_value_tag) {
        EXPECT_EQ(got->value.float_value, sent.value.float_value);
    }
}

SatResponse uint_response(Status status, uint32_t offset, Width width,
                          uint32_t value)
{
    SatResponse rsp = SatResponse_init_zero;
    rsp.status = status;
    rsp.offset = offset;
    rsp.width = width;
    rsp.which_value = SatResponse_uint_value_tag;
    rsp.value.uint_value = value;
    return rsp;
}

SatResponse float_response(uint32_t offset, float value)
{
    SatResponse rsp = SatResponse_init_zero;
    rsp.status = Status_STATUS_OK;
    rsp.offset = offset;
    rsp.width = Width_WIDTH_F32;
    rsp.which_value = SatResponse_float_value_tag;
    rsp.value.float_value = value;
    return rsp;
}

TEST(CmdResponderTest, RoundTripsAUintResponse)
{
    expect_round_trip(uint_response(Status_STATUS_OK, 8, Width_WIDTH_U32,
                                    0xDEADBEEF));
}

TEST(CmdResponderTest, RoundTripsAFloatResponse)
{
    /* 1.0f is 00 00 80 3f on the wire, so this also exercises cobs standing
       in for zero bytes in the middle of a frame. */
    expect_round_trip(float_response(12, 1.0f));
}

TEST(CmdResponderTest, RoundTripsAnErrorWithNoValue)
{
    SatResponse rsp = SatResponse_init_zero;
    rsp.status = Status_STATUS_BAD_OFFSET;
    rsp.offset = 0xFFFF;
    expect_round_trip(rsp);
}

TEST(CmdResponderTest, KeepsAZeroValuedOneof)
{
    /* proto3 drops zero valued fields, but a set oneof arm is presence
       information, so nanopb must keep this one. If it ever stopped, a read
       of a zeroed field would come back looking like it had no value. */
    expect_round_trip(uint_response(Status_STATUS_OK, 0, Width_WIDTH_U8, 0));
}

TEST(CmdResponderTest, AnAllDefaultResponseStillMakesAFrame)
{
    /* Everything here is a proto3 default, so the message serializes to no
       bytes at all and the frame would be empty without CmdResponder's
       explicit status. The far end drops empty frames as stray delimiters,
       so this response would simply vanish. */
    expect_round_trip(SatResponse_init_zero);
}

TEST(CmdResponderTest, FramesAreDelimitedAndFreeOfZeros)
{
    UsbSim usb{};
    CmdResponder responder{usb};

    ASSERT_TRUE(responder.send(uint_response(Status_STATUS_OK, 1,
                                             Width_WIDTH_U16, 0)));

    std::vector<uint8_t> wire;
    uint8_t c{};
    while (usb.pop(c)) {
        wire.push_back(c);
    }

    ASSERT_FALSE(wire.empty());
    EXPECT_EQ(wire.back(), 0); // the delimiter, and the only zero
    for (std::size_t i = 0; i + 1 < wire.size(); i++) {
        EXPECT_NE(wire[i], 0);
    }
}

TEST(CmdResponderTest, SendsSeveralResponsesInOrder)
{
    UsbSim usb{};
    CmdResponder responder{usb};

    ASSERT_TRUE(responder.send(uint_response(Status_STATUS_OK, 1,
                                             Width_WIDTH_U8, 11)));
    ASSERT_TRUE(responder.send(uint_response(Status_STATUS_OK, 2,
                                             Width_WIDTH_U8, 22)));

    std::optional<SatResponse> first = recv_response(usb);
    std::optional<SatResponse> second = recv_response(usb);
    ASSERT_TRUE(first.has_value());
    ASSERT_TRUE(second.has_value());
    EXPECT_EQ(first->offset, 1u);
    EXPECT_EQ(second->offset, 2u);
}

TEST(CmdResponderTest, ReportsAFullQueueAndCleansUpTheTornFrame)
{
    /* Only room for one of these frames plus change, so the second send
       runs out of space partway through and leaves a fragment behind. */
    RingBuffer<uint8_t, 16> tiny{};
    CmdResponder responder{tiny};

    const SatResponse rsp = uint_response(Status_STATUS_OK, 8,
                                          Width_WIDTH_U32, 42);
    ASSERT_TRUE(responder.send(rsp));
    EXPECT_FALSE(responder.send(rsp));

    /* The ground reads the link dry, fragment and all. */
    uint8_t c{};
    while (tiny.pop(c)) {
    }

    /* The next send closes the fragment off with a delimiter of its own
       before writing its frame, so the frame arrives intact. */
    ASSERT_TRUE(responder.send(rsp));
    ASSERT_TRUE(tiny.pop(c));
    EXPECT_EQ(c, 0);

    std::optional<SatResponse> got = recv_response(tiny);
    ASSERT_TRUE(got.has_value());
    EXPECT_EQ(got->offset, 8u);
    EXPECT_EQ(got->value.uint_value, 42u);
}

} // namespace
