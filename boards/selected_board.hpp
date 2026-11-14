#pragma once
/**
 * Picks the board this image is built for. This is the only place the
 * board macro is read. boards/BUILD.bazel defines SATS_BOARD_PICO or
 * SATS_BOARD_PICUBED from the board platform that --config=pico or
 * --config=picubed selects (see //platforms/boards).
 *
 * Apps include this header; boards include only boards/board.hpp, so a
 * board's header never sees which board was selected.
 *
 * Use driver accessors and nullptr checks to write board-agnostic code.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include "boards/board.hpp"

#if defined(SATS_BOARD_PICO) + defined(SATS_BOARD_PICUBED) != 1
#error "Select exactly one board: build with --config=pico or --config=picubed"
#endif

#if defined(SATS_BOARD_PICO)
#include "boards/pico/pico_board.hpp"
using SelectedBoard = PicoBoard;
#elif defined(SATS_BOARD_PICUBED)
#include "boards/picubed/picubed_board.hpp"
using SelectedBoard = PicubedBoard;
#endif
