#pragma once
/**
 * Author: Carson Lauer
 * Date: 11 September 2026
 */

#include <stdint.h>

#include <cstring>
#include <vector>

#include "common/fs/block_device.hpp"

/**
 * A nor flash chip in memory, so the wiring in LfsStorage can be tested on
 * the host without a board.
 *
 * Faithful about the two things that catch a mistake in that wiring:
 * everything is granular, and programming clears bits without being able to
 * set them. An offset computed wrongly therefore shows up as data that will
 * not read back, rather than as a write that quietly lands somewhere else.
 */
class RamBlockDevice : public BlockDevice
{
public:
    /* Defaults are the rp2350's: 4 KiB erase blocks, 256 byte pages. */
    RamBlockDevice(uint32_t size, uint32_t erase_size = 4096,
                   uint32_t program_size = 256)
        : mem_(size, 0xFF), erase_size_(erase_size), program_size_(program_size)
    {}

    uint32_t size() const override
    {
        return static_cast<uint32_t>(mem_.size());
    }

    uint32_t erase_size() const override
    {
        return erase_size_;
    }

    uint32_t program_size() const override
    {
        return program_size_;
    }

    bool read(uint32_t offset, void *dst, uint32_t len) const override
    {
        if (!in_bounds(offset, len)) {
            return false;
        }
        std::memcpy(dst, mem_.data() + offset, len);
        return true;
    }

    bool program(uint32_t offset, const void *src, uint32_t len) override
    {
        if (!in_bounds(offset, len)) {
            return false;
        }
        if (offset % program_size_ != 0 || len % program_size_ != 0) {
            return false;
        }

        const uint8_t *in = static_cast<const uint8_t *>(src);
        for (uint32_t i = 0; i < len; i++) {
            mem_[offset + i] &= in[i];
        }
        return true;
    }

    bool erase(uint32_t offset, uint32_t len) override
    {
        if (!in_bounds(offset, len)) {
            return false;
        }
        if (offset % erase_size_ != 0 || len % erase_size_ != 0) {
            return false;
        }

        std::memset(mem_.data() + offset, 0xFF, len);
        return true;
    }

private:
    bool in_bounds(uint32_t offset, uint32_t len) const
    {
        return offset <= mem_.size() && len <= mem_.size() - offset;
    }

    std::vector<uint8_t> mem_;
    uint32_t erase_size_;
    uint32_t program_size_;
};
