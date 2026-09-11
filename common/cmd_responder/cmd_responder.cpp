/**
 * Author: Carson Lauer
 * Date: 10 September 2026
 */
#include "cmd_responder.hpp"

#include "stdint.h"

#include <array>

#include "common/cobs/cobs.hpp"
#include "common/util/queue.hpp"

#include "pb_encode.h"
#include "proto/sats_command.pb.h"

CmdResponder::CmdResponder(Queue<uint8_t> &out) : out_(out) {}

bool CmdResponder::send(const SatResponse &rsp)
{
    std::array<uint8_t, SatResponse_size> payload{};
    pb_ostream_t stream =
        pb_ostream_from_buffer(payload.data(), payload.size());
    if (!pb_encode(&stream, &SatResponse_msg, &rsp)) {
        return false;
    }
    std::size_t len = stream.bytes_written;

    /* proto3 leaves zero valued fields out, so an all default response
       serializes to nothing and the far end would throw the resulting empty
       frame away as a stray delimiter. Spell `status` out by hand instead:
       it decodes back to the very same message, just not canonically. */
    if (len == 0) {
        payload[0] = SatResponse_status_tag << 3; // field 1, varint
        payload[1] = Status_STATUS_UNSPECIFIED;
        len = 2;
    }

    std::array<uint8_t, kMaxFrameSize> frame{};
    const uint32_t n = cobs_encode(payload.data(), len, frame.data());

    /* A frame cut short by a full queue never got its delimiter, so it would
       run into the next frame and take that one down with it. Close it off
       here and the far end drops just the fragment, as an empty or
       undecodable frame, then resyncs on the frame we are about to write. */
    if (torn_) {
        if (!out_.push(0)) {
            return false;
        }
        torn_ = false;
    }

    for (uint32_t i = 0; i < n; i++) {
        if (!out_.push(frame[i])) {
            torn_ = true;
            return false;
        }
    }

    if (!out_.push(0)) {
        torn_ = true;
        return false;
    }
    return true;
}
