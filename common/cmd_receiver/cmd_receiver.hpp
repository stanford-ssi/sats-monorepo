#pragma once
/**
 * Author: Carson Lauer
 * Date: 8 September 2026
 */

#include "stdint.h"

#include <array>
#include <cstddef>
#include <optional>

#include "pb_decode.h"
#include "proto/sats_command.pb.h"

#include "common/util/ring_buffer.hpp"
#include "common/util/queue.hpp"

/**
 * Reassembles SatCmds from a stream of cobs encoded bytes.
 *
 * Bytes are pulled from `in` (usb on flight hardware, a ring buffer in the
 * unit tests) and cobs decoded one at a time. A zero byte delimits a frame;
 * every complete frame is run through nanopb and queued up for get_cmd().
 */
class CmdReceiver
{
public:
    CmdReceiver(Queue<uint8_t> &in);

    CmdReceiver(CmdReceiver &&other) = delete;
    CmdReceiver(const CmdReceiver &other) = delete;
    CmdReceiver &operator=(CmdReceiver &&other) = delete;
    CmdReceiver &operator=(const CmdReceiver &cmd) = delete;

    /**
     * Drain the input queue, decoding whatever has arrived. Returns the
     * number of complete commands that were queued up for get_cmd().
     */
    uint32_t update();

    /**
     * Pop the oldest decoded command, or nothing if none are pending.
     */
    std::optional<SatCmd> get_cmd();

private:
    /* Longest frame we are willing to reassemble. A SatCmd is 14 bytes at
       most, so this leaves plenty of room for the contract to grow. */
    static constexpr std::size_t kMaxFrameSize = 256;
    static_assert(SatCmd_size <= kMaxFrameSize, "frames would never fit");

    Queue<uint8_t> &in_;

    /* Cobs decoder state, see decode_c(). */
    int code_{}; // length of the block being decoded, code byte included
    int pos_{};  // bytes of that block consumed so far, code byte included

    /* The frame being reassembled, decoded but not yet delimited. */
    std::array<uint8_t, kMaxFrameSize> buf_{};
    std::size_t len_{};
    bool overflowed_{};

    RingBuffer<SatCmd, 8> cmd_buffer_{};

    std::optional<uint8_t> decode_c(uint8_t next);
    bool finish_frame();
};
