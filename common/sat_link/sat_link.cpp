/**
 * Author: Carson Lauer
 * Date: 25 October 2026
 */
#include "sat_link.hpp"

#include "stdint.h"

#include <array>

#include "common/cobs/cobs.hpp"
#include "common/util/queue.hpp"

#include "pb_decode.h"
#include "pb_encode.h"
#include "proto/sats_command.pb.h"

SatLink::SatLink(Queue<uint8_t> &in, Queue<uint8_t> &out) : in_(in), out_(out)
{}

uint32_t SatLink::update()
{
    uint32_t msgs = 0;
    uint8_t c{};
    while (in_.pop(c)) {
        /* Zero never appears inside an encoded frame, so it delimits one. */
        if (c == 0) {
            if (finish_frame()) {
                msgs++;
            }
            continue;
        }

        std::optional<uint8_t> decoded = decode_c(c);
        if (!decoded) {
            continue;
        }

        if (len_ < buf_.size()) {
            buf_[len_++] = decoded.value();
        } else {
            /* Too long to be one of ours; remember to drop it at the
               delimiter rather than decoding a truncated prefix. */
            overflowed_ = true;
        }
    }
    return msgs;
}

std::optional<SatMsg> SatLink::receive()
{
    SatMsg msg = SatMsg_init_zero;
    if (!inbox_.pop(msg)) {
        return {};
    }
    return msg;
}

bool SatLink::send(const SatMsg &msg)
{
    std::array<uint8_t, SatMsg_size> payload{};
    pb_ostream_t stream =
        pb_ostream_from_buffer(payload.data(), payload.size());
    if (!pb_encode(&stream, &SatMsg_msg, &msg)) {
        return false;
    }

    /* Every real message has a non zero kind, so it never encodes to
       nothing. One that did would frame as a lone delimiter, which the far
       end throws away as a stray, so refuse it here instead. */
    if (stream.bytes_written == 0) {
        return false;
    }

    std::array<uint8_t, kMaxEncodedSize> frame{};
    const uint32_t n =
        cobs_encode(payload.data(), stream.bytes_written, frame.data());

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

/**
 * Feed one non delimiter byte to the cobs decoder.
 *
 * Cobs splits the payload into blocks of up to 254 non zero bytes, each
 * prefixed by a code byte holding the block length (code byte included). A
 * block shorter than 0xff stands in for a zero byte the encoder stripped out.
 *
 * Returns the decoded byte, or nothing when `next` was a code byte that did
 * not stand in for a zero.
 */
std::optional<uint8_t> SatLink::decode_c(uint8_t next)
{
    if (pos_ < code_) {
        pos_++;
        return next; // plain payload byte inside the current block
    }

    /* The previous block is done, so `next` starts a new one. */
    const bool zero_stripped = (code_ != 0 && code_ != 0xff);
    code_ = next;
    pos_ = 1;
    return zero_stripped ? std::optional<uint8_t>{0} : std::nullopt;
}

/**
 * Hand the reassembled frame to nanopb and reset for the next one. Returns
 * true if a message was queued up.
 */
bool SatLink::finish_frame()
{
    const std::size_t len = len_;
    const bool usable = !overflowed_;

    code_ = 0;
    pos_ = 0;
    len_ = 0;
    overflowed_ = false;

    /* An empty frame is just a stray delimiter, e.g. an idle link. */
    if (!usable || len == 0) {
        return false;
    }

    SatMsg msg = SatMsg_init_zero;
    pb_istream_t stream = pb_istream_from_buffer(buf_.data(), len);
    if (!pb_decode(&stream, &SatMsg_msg, &msg)) {
        return false;
    }

    return inbox_.push(msg);
}
