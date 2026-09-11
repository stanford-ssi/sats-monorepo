/**
 * Author: Carson Lauer
 * Date: 8 September 2026 
 */
#include "cmd_receiver.hpp"

#include "stdint.h"
#include "common/util/queue.hpp"

#include "pb_decode.h"
#include "proto/sats_command.pb.h"


CmdReceiver::CmdReceiver(Queue<uint8_t>& in) :
    in_(in) { }

uint32_t CmdReceiver::update()
{
    uint32_t cmds = 0;
    uint8_t c{};
    while (in_.pop(c))
    {
        /* Zero never appears inside an encoded frame, so it delimits one. */
        if (c == 0) {
            if (finish_frame()) {
                cmds++;
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
    return cmds;
}

std::optional<SatCmd> CmdReceiver::get_cmd()
{
    SatCmd cmd = SatCmd_init_zero;
    if (!cmd_buffer_.pop(cmd)) {
        return {};
    }
    return cmd;
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
std::optional<uint8_t> CmdReceiver::decode_c(uint8_t next)
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
 * true if a command was queued up.
 */
bool CmdReceiver::finish_frame()
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

    SatCmd cmd = SatCmd_init_zero;
    pb_istream_t stream = pb_istream_from_buffer(buf_.data(), len);
    if (!pb_decode(&stream, &SatCmd_msg, &cmd)) {
        return false;
    }

    return cmd_buffer_.push(cmd);
}
