#pragma once

#include <cstdint>

struct PowerInfo
{
    float voltage{};
    float current{};
};

/*
 * What the loop is currently doing. An enum rather than a magic number, and
 * the ground gets the names for free: satui reads the enumerators out of
 * the debug info, so `mode` shows as SAFE and can be written as either
 * `SAFE` or `2` without the command set knowing enums exist.
 *
 * The underlying type is fixed so the offset of everything after it does
 * not move with the compiler's choice, and so the ground addresses it as
 * the one byte it is.
 */
enum class Mode : uint8_t
{
    BOOT = 0,
    NOMINAL = 1,
    SAFE = 2,
};

struct Slate
{
    uint32_t sleep_ms{250};
    uint32_t cycle_counter{};
    int signed_scratch{};
    float temperature{};
    PowerInfo board_power{};
    bool led_enabled{true};
    Mode mode{Mode::BOOT};
};
