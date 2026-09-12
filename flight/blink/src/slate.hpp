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

    int32_t rust_test_a{};
    int32_t rust_test_b{};
    int32_t rust_result{};

    /* The filesystem demo. `boot_count` and the two settings above it are
       restored from flash at startup, so power cycling the board shows up
       here rather than resetting it. Writing `save_settings` from the
       ground is what commits the current sleep_ms and led_enabled for the
       next boot; the firmware clears it once the write has landed. */
    bool save_settings{false};
    uint32_t boot_count{};
    /* Where the filesystem region starts, as an offset into the chip. Read
       off the board rather than worked out on the ground, since it moves
       with whatever the build thinks the flash size is. */
    uint32_t fs_base{};
    uint32_t fs_bytes_free{};
    /* The last thing littlefs said: 0 for fine, otherwise one of the
       negative LFS_ERR codes listed in lfs.h. */
    int32_t fs_error{};
};
