/**
 * Author: Carson Lauer
 * Date: 8 September 2026 
 */
#include "cmd_receiver.hpp"

#include "stdint.h"
#include "queue.hpp"

#include "pb_decode.h"
#include "proto/sats_command.pb.h"


CmdReceiver::CmdReceiver() :
    overhead_state_(0),
    pos_(0) { }

uint32_t CmdReceiver::update(Queue<uint8_t> &in)
{
    uint32_t count = 0;
    while (!in.empty())
    {
        uint8_t c{};
        in.pop(c);

        std::optional<uint8_t> possible_next = decode_c(c);
        if (possible_next) {
            buf_.push(possible_next.value());
            count++;
        }
    }
    return count;
}

std::optional<SatCmd> CmdReceiver::get_cmd()
{
    return {};
}

std::optional<uint8_t> CmdReceiver::decode_c(uint8_t next) {
    if (pos_ == 0) {
        overhead_state_ = next;
        pos_++;
        return {};
    }
    return {};
}

