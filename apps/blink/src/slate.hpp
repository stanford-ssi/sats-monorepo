#pragma once

struct PowerInfo {
    float voltage{};
    float current{};
};

struct Slate {
    uint32_t sleep_ms{250};
    float temperature{};
    PowerInfo board_power{};
};


