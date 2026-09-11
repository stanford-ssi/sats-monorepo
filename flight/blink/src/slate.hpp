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
    float temperature{};
    PowerInfo board_power{};
    bool led_enabled{true};
};
