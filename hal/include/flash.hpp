#pragma once
/**
 * Author: Carson Lauer
 * Date: 11 September 2026
 */
#include <stdint.h>

#include "common/fs/block_device.hpp"

/**
 * The board's own program flash, as a block device.
 *
 * The region sits at the very top of the chip, as far as it can get from
 * the program image at the bottom, and the constructor refuses to hand out
 * a region that a growing firmware image has run into. Erasing and
 * programming stop the processor for as long as they take and cannot happen
 * with interrupts on, so this is for startup and for deliberate save
 * points, not for a control loop.
 *
 * Everything past the constructor is the BlockDevice interface, so the
 * filesystem above it never learns which chip it is talking to.
 */
class Flash : public BlockDevice
{
public:
    /* Thirty two erase blocks. littlefs gives a file a block of its own
       once it outgrows its metadata and moves metadata around to spread
       the wear, so it wants blocks to play with rather than the tightest
       region that would hold the files. */
    static constexpr uint32_t kDefaultSize = 128 * 1024;

    /**
     * Claim `size_bytes` at the top of flash, rounded down to a whole
     * number of erase blocks.
     *
     * A region that would overlap the program image comes back with a
     * size of 0 rather than a region that works until the next time the
     * firmware grows; mounting a filesystem on it then fails cleanly.
     */
    explicit Flash(uint32_t size_bytes = kDefaultSize);

    uint32_t size() const override;
    uint32_t erase_size() const override;
    uint32_t program_size() const override;

    bool read(uint32_t offset, void *dst, uint32_t len) const override;

    /* `src` has to be in ram: the rom routine that does the programming
       reads it while the flash is not answering to the memory bus. */
    bool program(uint32_t offset, const void *src, uint32_t len) override;

    bool erase(uint32_t offset, uint32_t len) override;

    /* Where the region starts, as an offset into the chip, for pointing
       picotool at it. */
    uint32_t base() const;

private:
    uint32_t base_{};
    uint32_t size_{};
};
