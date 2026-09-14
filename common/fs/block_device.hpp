#pragma once
/**
 * Author: Carson Lauer
 * Date: 11 September 2026
 */

#include <stdint.h>

/**
 * A flash chip, as a filesystem needs to see one.
 *
 * The three properties of nor flash that shape everything above it are all
 * exposed here: reads are random access, writes only go down in whole
 * pages, and a page cannot be rewritten until a much larger block around
 * it has been erased back to all ones.
 *
 * Offsets are relative to the start of the device, so an implementation is
 * free to be a window into part of a chip and whatever is layered on top
 * never learns where that window sits. No virtual destructor, same as
 * Queue: these are held by reference for the life of the program and never
 * deleted through a base pointer.
 */
class BlockDevice
{
public:
    /* Total addressable bytes, always a whole number of erase blocks. */
    virtual uint32_t size() const = 0;

    /* Smallest region erase() can clear, and the alignment it requires. */
    virtual uint32_t erase_size() const = 0;

    /* Smallest region program() can write, and the alignment it requires. */
    virtual uint32_t program_size() const = 0;

    /* Reads are unaligned and arbitrary length. False means the request
       was out of bounds or the read itself failed. */
    virtual bool read(uint32_t offset, void *dst, uint32_t len) const = 0;

    /**
     * Writes `len` bytes at `offset`, both of which must be multiples of
     * program_size().
     *
     * Only meaningful on erased bytes. Programming clears bits and cannot
     * set them, so writing over live data silently ands the two together
     * rather than failing; staying on erased ground is the caller's job.
     */
    virtual bool program(uint32_t offset, const void *src, uint32_t len) = 0;

    /* Clears `len` bytes back to 0xFF. Both arguments must be multiples of
       erase_size(). */
    virtual bool erase(uint32_t offset, uint32_t len) = 0;
};
