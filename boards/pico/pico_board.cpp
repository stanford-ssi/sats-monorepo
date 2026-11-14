/**
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include "boards/pico/pico_board.hpp"
#include "boards/pico/pins.hpp"

PicoBoard::PicoBoard() : led_(PicoPins::kLed, false) {}
