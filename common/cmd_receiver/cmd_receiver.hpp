#pragma once
/**
 * Author: Carson Lauer
 * Date: 8 September 2026
 */

#include "ring_buffer.hpp"

#include "stdint.h"

#include <optional>

#include "pb_decode.h"
#include "proto/sats_command.pb.h"

#include "queue.hpp"

class CmdReceiver
{
public:
    CmdReceiver();

    CmdReceiver(CmdReceiver &&other) = delete;
    CmdReceiver(const CmdReceiver &other) = delete;
    CmdReceiver &operator=(CmdReceiver &&other) = delete;
    CmdReceiver &operator=(const CmdReceiver &cmd) = delete;
    
    uint32_t update(Queue<uint8_t> &in);
    std::optional<SatCmd> get_cmd();
private:
    int overhead_state_{}; 
    int pos_{};
    RingBuffer<uint8_t, 256> buf_{};
    RingBuffer<SatCmd, 8> cmd_buffer_{};

    std::optional<uint8_t> decode_c(uint8_t next);
};
