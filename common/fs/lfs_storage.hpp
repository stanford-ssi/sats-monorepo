#pragma once
/**
 * Author: Carson Lauer
 * Date: 11 September 2026
 */

#include <stdint.h>

#include "lfs.h"

#include "common/fs/block_device.hpp"

/**
 * The storage littlefs runs on, for a given BlockDevice.
 *
 * This is not a layer over littlefs and nothing here wraps it. It is the
 * block device littlefs asks to be given, filled in: the block and offset
 * addressing of its callbacks translated into the byte offsets a
 * BlockDevice takes, and the buffers it cannot allocate for itself, since
 * it is built with LFS_NO_MALLOC.
 *
 * An object rather than a function because of those buffers. lfs_config
 * holds pointers to them, so they have to outlive every call littlefs
 * makes; bundling them with the config it points into is what guarantees
 * that, and is why this cannot be copied.
 *
 * Geometry comes from the device rather than from constants here, so the
 * same wiring works on the rp2350's internal flash and on a test double.
 * Use it with the littlefs api directly:
 *
 *     LfsStorage device{flash};
 *     lfs_t lfs;
 *     int err = lfs_mount(&lfs, device.config());
 *
 * Nothing here is thread or interrupt safe, and neither is littlefs
 * without LFS_THREADSAFE.
 */
class LfsStorage
{
public:
    /* The most this will cache in ram for reads, writes and each open
       file. The device's own page size is used when it is smaller, which
       is what littlefs wants: its cache has to be a multiple of the
       program size and a factor of the erase block. */
    static constexpr uint32_t kCacheSize = 256;

    explicit LfsStorage(BlockDevice &dev);

    LfsStorage(LfsStorage &&other) = delete;
    LfsStorage(const LfsStorage &other) = delete;
    LfsStorage &operator=(LfsStorage &&other) = delete;
    LfsStorage &operator=(const LfsStorage &other) = delete;

    /**
     * The configuration to hand lfs_mount() and lfs_format().
     *
     * Null when the device is not one littlefs can be configured for: no
     * pages, pages bigger than the cache, an erase block that is not a
     * whole number of pages, or fewer than two blocks. There is nothing to
     * mount in that case, which is the only failure this can report.
     */
    const lfs_config *config() const;

private:
    static int read_block(const lfs_config *c, lfs_block_t block, lfs_off_t off,
                          void *buffer, lfs_size_t size);
    static int prog_block(const lfs_config *c, lfs_block_t block, lfs_off_t off,
                          const void *buffer, lfs_size_t size);
    static int erase_block(const lfs_config *c, lfs_block_t block);
    static int sync_device(const lfs_config *c);

    BlockDevice &dev_;
    lfs_config config_{};
    bool usable_{false};

    uint8_t read_buffer_[kCacheSize]{};
    uint8_t prog_buffer_[kCacheSize]{};
    /* A bitmap of blocks the allocator has looked ahead at, one bit each,
       so this tracks 128 of them. Not a limit on anything, just how much
       of the disk one allocation pass covers. */
    uint8_t lookahead_buffer_[16]{};
};

/**
 * The cache littlefs needs for one open file.
 *
 * One of these per file open at the same time, handed to
 * lfs_file_opencfg(); with no heap to take it from, littlefs cannot make
 * its own. lfs_file_open() is not usable in this build for the same
 * reason.
 */
class LfsFileBuffer
{
public:
    LfsFileBuffer();

    const lfs_file_config *config() const;

private:
    lfs_file_config config_{};
    uint8_t buffer_[LfsStorage::kCacheSize]{};
};
