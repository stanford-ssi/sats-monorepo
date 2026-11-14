/**
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include "boards/picubed/picubed_board.hpp"
#include "boards/picubed/pins.hpp"

PicubedBoard::PicubedBoard()
    : burn_a_(PicubedPins::kBurnA, false), burn_b_(PicubedPins::kBurnB, false),
      burn_relay_(PicubedPins::kBurnRelay, false),
      burn_wire_(burn_a_, burn_b_, burn_relay_, clock_),
      led_(PicubedPins::kLed, false)
{}
