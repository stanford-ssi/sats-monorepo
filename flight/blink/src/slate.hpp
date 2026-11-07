#pragma once

#include <cstdint>

struct PowerInfo
{
    float voltage{};
    float current{};
};

struct Slate
{
    uint32_t sleep_ms{250};
    uint32_t cycle_counter{};
    int signed_scratch{};
    float temperature{};
    PowerInfo board_power{};
    bool led_enabled{true};

    /* An end to end check: the loop keeps c = a + b, so the ground can
       write a and b and confirm the board did the arithmetic. */
    int32_t a{};
    int32_t b{};
    int32_t c{};
};
