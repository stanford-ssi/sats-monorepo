#pragma once
/**
 * Author: Carson Lauer
 * Date: 10 September 2026
 */

#include "stdint.h"

#include <cstddef>

#include "proto/sats_command.pb.h"

#include "common/util/queue.hpp"

/**
 * Serializes SatResponses onto a cobs framed byte stream.
 *
 * The mirror of CmdReceiver: every response is encoded by nanopb, cobs
 * encoded, and pushed onto `out` (usb on flight hardware, a ring buffer in
 * the unit tests) followed by the zero byte that delimits the frame.
 */
class CmdResponder
{
public:
    explicit CmdResponder(Queue<uint8_t> &out);

    CmdResponder(CmdResponder &&other) = delete;
    CmdResponder(const CmdResponder &other) = delete;
    CmdResponder &operator=(CmdResponder &&other) = delete;
    CmdResponder &operator=(const CmdResponder &other) = delete;

    /**
     * Encode, frame and enqueue one response. Returns false if nanopb
     * refused the message or `out` would not take the whole frame.
     */
    bool send(const SatResponse &rsp);

private:
    /* Cobs adds a code byte every 254 payload bytes, plus a leading one. */
    static constexpr std::size_t kMaxFrameSize =
        SatResponse_size + SatResponse_size / 254 + 2;

    Queue<uint8_t> &out_;

    /* A frame we could not finish writing, see send(). */
    bool torn_{};
};
