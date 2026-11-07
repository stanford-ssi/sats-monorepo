#pragma once
/**
 * Author: Carson Lauer
 * Date: 25 October 2026
 */

#include "stdint.h"

#include <array>
#include <cstddef>
#include <optional>

#include "pb.h"
#include "pb_decode.h"
#include "pb_encode.h"
#include "proto/sats_command.pb.h"

#include "common/cobs/cobs.hpp"
#include "common/util/queue.hpp"
#include "common/util/ring_buffer.hpp"

/**
 * What SatLink needs to know about a nanopb message type: its field
 * descriptor and the longest it can encode to. nanopb only generates these
 * as C globals named after the message, so each message a link carries
 * gets a specialisation here.
 */
template <typename Msg>
struct NanopbTraits; // deliberately undefined: an unlisted type won't compile

template <>
struct NanopbTraits<SatMsg>
{
    static const pb_msgdesc_t *fields()
    {
        return &SatMsg_msg;
    }
    static constexpr std::size_t max_size = SatMsg_size;
};

/**
 * One end of a cobs framed nanopb link: RxMsgs in, TxMsgs out.
 *
 * The two types are separate so a link can be asymmetric, but SatCmd is
 * symmetric, so on every link today both are SatMsg: whatever arrives on
 * `in` is decoded and queued for receive(), be it a request to answer or
 * the answer to a request we sent; send() frames a message of either kind
 * onto `out`. On usb `in` and `out` are the same queue; in the unit tests
 * they are two ring buffers.
 */
template <typename RxMsg, typename TxMsg>
class SatLink
{
    using Rx = NanopbTraits<RxMsg>;
    using Tx = NanopbTraits<TxMsg>;

public:
    SatLink(Queue<uint8_t> &in, Queue<uint8_t> &out) : in_(in), out_(out) {}

    SatLink(SatLink &&other) = delete;
    SatLink(const SatLink &other) = delete;
    SatLink &operator=(SatLink &&other) = delete;
    SatLink &operator=(const SatLink &other) = delete;

    /**
     * Drain `in`, decoding whatever has arrived. Returns the number of
     * complete messages that were queued up for receive().
     */
    uint32_t update()
    {
        uint32_t msgs = 0;
        uint8_t c{};
        while (in_.pop(c)) {
            /* Zero never appears inside an encoded frame, so it delimits
               one. */
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

    /**
     * Pop the oldest decoded message, or nothing if none are pending.
     */
    std::optional<RxMsg> receive()
    {
        RxMsg msg{};
        if (!inbox_.pop(msg)) {
            return {};
        }
        return msg;
    }

    /**
     * Encode, frame and enqueue one message. Returns false if nanopb
     * refused it or `out` would not take the whole frame.
     */
    bool send(const TxMsg &msg)
    {
        std::array<uint8_t, Tx::max_size> payload{};
        pb_ostream_t stream =
            pb_ostream_from_buffer(payload.data(), payload.size());
        if (!pb_encode(&stream, Tx::fields(), &msg)) {
            return false;
        }

        /* A message with every field at its default encodes to nothing,
           which would frame as a lone delimiter that the far end throws
           away as a stray, so refuse it here instead. */
        if (stream.bytes_written == 0) {
            return false;
        }

        std::array<uint8_t, kMaxEncodedSize> frame{};
        const uint32_t n =
            cobs_encode(payload.data(), stream.bytes_written, frame.data());

        /* A frame cut short by a full queue never got its delimiter, so it
           would run into the next frame and take that one down with it.
           Close it off here and the far end drops just the fragment, as an
           empty or undecodable frame, then resyncs on the frame we are
           about to write. */
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

private:
    /* Longest frame we are willing to reassemble. A SatMsg is a couple of
       dozen bytes at most, so this leaves plenty of room to grow. */
    static constexpr std::size_t kMaxFrameSize = 256;
    static_assert(Rx::max_size <= kMaxFrameSize, "frames would never fit");

    /* Cobs adds a code byte every 254 payload bytes, plus a leading one. */
    static constexpr std::size_t kMaxEncodedSize =
        Tx::max_size + Tx::max_size / 254 + 2;

    Queue<uint8_t> &in_;
    Queue<uint8_t> &out_;

    /* Cobs decoder state, see decode_c(). */
    int code_{}; // length of the block being decoded, code byte included
    int pos_{};  // bytes of that block consumed so far, code byte included

    /* The frame being reassembled, decoded but not yet delimited. */
    std::array<uint8_t, kMaxFrameSize> buf_{};
    std::size_t len_{};
    bool overflowed_{};

    RingBuffer<RxMsg, 8> inbox_{};

    /* A frame we could not finish writing, see send(). */
    bool torn_{};

    /**
     * Feed one non delimiter byte to the cobs decoder.
     *
     * Cobs splits the payload into blocks of up to 254 non zero bytes, each
     * prefixed by a code byte holding the block length (code byte
     * included). A block shorter than 0xff stands in for a zero byte the
     * encoder stripped out.
     *
     * Returns the decoded byte, or nothing when `next` was a code byte that
     * did not stand in for a zero.
     */
    std::optional<uint8_t> decode_c(uint8_t next)
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
     * Hand the reassembled frame to nanopb and reset for the next one.
     * Returns true if a message was queued up.
     */
    bool finish_frame()
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

        RxMsg msg{};
        pb_istream_t stream = pb_istream_from_buffer(buf_.data(), len);
        if (!pb_decode(&stream, Rx::fields(), &msg)) {
            return false;
        }

        return inbox_.push(msg);
    }
};
