#pragma once
/**
 * Author: Carson Lauer
 * Date: 25 October 2026
 */

#include "stdint.h"

#include <array>
#include <cstddef>
#include <optional>

#include "proto/sats_command.pb.h"

#include "common/util/queue.hpp"
#include "common/util/ring_buffer.hpp"

/**
 * One end of a SatCmd link: SatMsgs in both directions over a cobs framed
 * byte stream.
 *
 * The protocol is symmetric, so there is no ground or flight flavour of
 * this. Whatever arrives on `in` is decoded and queued for receive(), be it
 * a request to answer or the answer to a request we sent; send() frames a
 * message of either kind onto `out`. On usb `in` and `out` are the same
 * queue; in the unit tests they are two ring buffers.
 */
class SatLink
{
public:
    SatLink(Queue<uint8_t> &in, Queue<uint8_t> &out);

    SatLink(SatLink &&other) = delete;
    SatLink(const SatLink &other) = delete;
    SatLink &operator=(SatLink &&other) = delete;
    SatLink &operator=(const SatLink &other) = delete;

    /**
     * Drain `in`, decoding whatever has arrived. Returns the number of
     * complete messages that were queued up for receive().
     */
    uint32_t update();

    /**
     * Pop the oldest decoded message, or nothing if none are pending.
     */
    std::optional<SatMsg> receive();

    /**
     * Encode, frame and enqueue one message. Returns false if nanopb
     * refused it or `out` would not take the whole frame.
     */
    bool send(const SatMsg &msg);

private:
    /* Longest frame we are willing to reassemble. A SatMsg is a couple of
       dozen bytes at most, so this leaves plenty of room to grow. */
    static constexpr std::size_t kMaxFrameSize = 256;
    static_assert(SatMsg_size <= kMaxFrameSize, "frames would never fit");

    /* Cobs adds a code byte every 254 payload bytes, plus a leading one. */
    static constexpr std::size_t kMaxEncodedSize =
        SatMsg_size + SatMsg_size / 254 + 2;

    Queue<uint8_t> &in_;
    Queue<uint8_t> &out_;

    /* Cobs decoder state, see decode_c(). */
    int code_{}; // length of the block being decoded, code byte included
    int pos_{};  // bytes of that block consumed so far, code byte included

    /* The frame being reassembled, decoded but not yet delimited. */
    std::array<uint8_t, kMaxFrameSize> buf_{};
    std::size_t len_{};
    bool overflowed_{};

    RingBuffer<SatMsg, 8> inbox_{};

    /* A frame we could not finish writing, see send(). */
    bool torn_{};

    std::optional<uint8_t> decode_c(uint8_t next);
    bool finish_frame();
};
