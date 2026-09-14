/**
 * Author: Carson Lauer
 * Date: 11 September 2026
 */

#include <cstring>

#include "hal/flash.hpp"

#include "hardware/flash.h"
#include "hardware/regs/addressmap.h"
#include "hardware/sync.h"
#include "pico.h"

#ifndef PICO_FLASH_SIZE_BYTES
#error "PICO_FLASH_SIZE_BYTES is unset; the board header should define it"
#endif

/* Provided by the linker script, one byte past the end of the program
   image. The filesystem region has to stay above it. */
extern "C" char __flash_binary_end;

namespace
{

uint32_t round_up(uint32_t value, uint32_t to)
{
    return ((value + to - 1) / to) * to;
}

} // namespace

Flash::Flash(uint32_t size_bytes)
{
    /* Whole erase blocks only. Anything else would hand the filesystem a
       region whose last block it could not clear without reaching past the
       end of it. */
    const uint32_t size = (size_bytes / FLASH_SECTOR_SIZE) * FLASH_SECTOR_SIZE;
    if (size == 0 || size > PICO_FLASH_SIZE_BYTES) {
        return; // stays 0 bytes long, which nothing can be mounted on
    }

    const uint32_t base = PICO_FLASH_SIZE_BYTES - size;

    /* The image is at the bottom of flash and the region at the top, so the
       two only meet if the firmware has grown into it. Refusing here turns
       that into a filesystem that will not mount, rather than a linker
       that quietly puts code where the next save is going to erase. */
    const uint32_t image_end = static_cast<uint32_t>(
        reinterpret_cast<uintptr_t>(&__flash_binary_end) - XIP_BASE);
    if (base < round_up(image_end, FLASH_SECTOR_SIZE)) {
        return;
    }

    base_ = base;
    size_ = size;
}

uint32_t Flash::base() const
{
    return base_;
}

uint32_t Flash::size() const
{
    return size_;
}

uint32_t Flash::erase_size() const
{
    return FLASH_SECTOR_SIZE;
}

uint32_t Flash::program_size() const
{
    return FLASH_PAGE_SIZE;
}

bool Flash::read(uint32_t offset, void *dst, uint32_t len) const
{
    if (offset > size_ || len > size_ - offset) {
        return false;
    }
    if (len == 0) {
        return true;
    }

    /* Straight out of the execute in place window. Both of the calls below
       flush the cache on their way out, so this cannot hand back a stale
       copy of something just written. */
    const uint8_t *src =
        reinterpret_cast<const uint8_t *>(XIP_BASE + base_ + offset);
    std::memcpy(dst, src, len);
    return true;
}

bool Flash::program(uint32_t offset, const void *src, uint32_t len)
{
    if (offset > size_ || len > size_ - offset || len == 0) {
        return false;
    }
    if (offset % FLASH_PAGE_SIZE != 0 || len % FLASH_PAGE_SIZE != 0) {
        return false;
    }

    /* The rom routine reads `src` with the flash disconnected from the
       memory bus, so a pointer into flash would be a pointer into nothing.
       Caught here rather than left as a hang. */
    const uintptr_t address = reinterpret_cast<uintptr_t>(src);
    if (address >= XIP_BASE && address < XIP_BASE + PICO_FLASH_SIZE_BYTES) {
        return false;
    }

    /* Interrupts off for the duration: the flash is not answering while
       this runs, and every interrupt handler on this board lives in it,
       usb stdio's timer callback included. */
    const uint32_t state = save_and_disable_interrupts();
    flash_range_program(base_ + offset, static_cast<const uint8_t *>(src), len);
    restore_interrupts(state);
    return true;
}

bool Flash::erase(uint32_t offset, uint32_t len)
{
    if (offset > size_ || len > size_ - offset || len == 0) {
        return false;
    }
    if (offset % FLASH_SECTOR_SIZE != 0 || len % FLASH_SECTOR_SIZE != 0) {
        return false;
    }

    const uint32_t state = save_and_disable_interrupts();
    flash_range_erase(base_ + offset, len);
    restore_interrupts(state);
    return true;
}
