#pragma once
/**
 * Author: Carson Lauer
 * Date: 25 October 2026
 */

#include <bit>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <optional>

#include "proto/sats_command.pb.h"

/**
 * Answers SatCmd READ and WRITE requests against a slate, by byte offset.
 *
 * There are no types here: a request names `width` bytes at `offset`, and
 * those bytes are copied in or out of the low end of `value`. Which bytes
 * mean a float and which a bool is the requester's business.
 *
 * The offset comes straight off the wire, so every access is bounds checked
 * and alignment checked before it touches memory; an unchecked offset would
 * be an arbitrary write from anyone who can talk to the radio. Templated on
 * the slate type so the bound is just sizeof(SlateT) and the whole thing is
 * host testable without any pico headers.
 */
template <typename SlateT>
class SlateServer
{
    /* The low `n` bytes of a uint64_t are its first `n` bytes in
       memory only on a little endian machine, which the rp2350 is. */
    static_assert(std::endian::native == std::endian::little,
                  "value is copied as little endian bytes");

public:
    explicit SlateServer(SlateT &slate) : slate_(slate) {}

    /**
     * Answer one message. Requests get a response carrying what the slate
     * holds afterwards, so a write is confirmed rather than assumed.
     * Anything that is not a request, such as the response to one of our
     * own, gets nothing; it is the caller's to route elsewhere.
     */
    std::optional<SatMsg> handle(const SatMsg &msg)
    {
        SatMsgType reply_type{};
        switch (msg.type) {
        case SatMsgType_SAT_MSG_TYPE_READ:
            reply_type = SatMsgType_SAT_MSG_TYPE_READ_RESPONSE;
            break;
        case SatMsgType_SAT_MSG_TYPE_WRITE:
            reply_type = SatMsgType_SAT_MSG_TYPE_WRITE_RESPONSE;
            break;
        default: return std::nullopt;
        }

        /* Offset and width are echoed on every reply, including the
           failures, so the requester can match a reply to its request. */
        SatMsg rsp = SatMsg_init_zero;
        rsp.type = reply_type;
        rsp.offset = msg.offset;
        rsp.width = msg.width;

        if (!valid_width(msg.width)) {
            rsp.status = Status_STATUS_BAD_WIDTH;
            return rsp;
        }
        /* Each Width is its own byte count, see the proto. */
        const std::size_t size = static_cast<std::size_t>(msg.width);
        if (!addressable(msg.offset, size)) {
            rsp.status = Status_STATUS_BAD_ADDRESS;
            return rsp;
        }

        uint8_t *field = reinterpret_cast<uint8_t *>(&slate_) + msg.offset;
        if (msg.type == SatMsgType_SAT_MSG_TYPE_WRITE) {
            /* Bytes past `size` are dropped, so an oversized value is
               truncated; the read back below reports what really landed. */
            std::memcpy(field, &msg.value, size);
        }

        rsp.status = Status_STATUS_OK;
        std::memcpy(&rsp.value, field, size);
        return rsp;
    }

private:
    SlateT &slate_;

    /* proto3 enums are open, so anything at all can arrive in `width`. */
    static bool valid_width(Width width)
    {
        switch (width) {
        case Width_WIDTH_1_BYTE:
        case Width_WIDTH_2_BYTES:
        case Width_WIDTH_4_BYTES:
        case Width_WIDTH_8_BYTES: return true;
        default: return false;
        }
    }

    /**
     * True if `size` bytes at `offset` lie wholly inside the slate and are
     * naturally aligned.
     *
     * The bound is a subtraction rather than `offset + size <= sizeof`,
     * which wraps around for an offset near the top of a uint32_t and would
     * wave through exactly the writes we are trying to stop. Misaligned
     * offsets are rejected too: memcpy would cope, but an aligned word is a
     * single store the loop can never observe half written, and a
     * misaligned one almost always means the requester's layout is wrong.
     */
    static bool addressable(uint32_t offset, std::size_t size)
    {
        if (sizeof(SlateT) < size) {
            return false;
        }
        return offset <= sizeof(SlateT) - size && (offset % size) == 0;
    }
};
