/**
 * Author: Carson Lauer
 * Date: 11 September 2026
 */

#include "common/fs/lfs_storage.hpp"

LfsStorage::LfsStorage(BlockDevice &dev) : dev_(dev)
{
    const uint32_t page = dev_.program_size();
    const uint32_t block = dev_.erase_size();

    if (page == 0 || page > kCacheSize || block == 0 || block % page != 0) {
        return;
    }
    if (dev_.size() / block < 2) {
        return;
    }

    config_.context = this;
    config_.read = &read_block;
    config_.prog = &prog_block;
    config_.erase = &erase_block;
    config_.sync = &sync_device;

    config_.read_size = page;
    config_.prog_size = page;
    config_.block_size = block;
    config_.block_count = dev_.size() / block;

    /* A page, so it is trivially a multiple of the read and program sizes
       and a factor of the block, which is what littlefs requires of it. */
    config_.cache_size = page;
    config_.lookahead_size = sizeof(lookahead_buffer_);

    /* How many erases a metadata block takes before littlefs moves it
       elsewhere. The upstream suggestion is 100 to 1000; the low end of
       that spreads the wear more evenly, which matters more here than the
       writes it costs, because there is very little of this region and the
       settings file is rewritten on every boot. */
    config_.block_cycles = 100;

    config_.read_buffer = read_buffer_;
    config_.prog_buffer = prog_buffer_;
    config_.lookahead_buffer = lookahead_buffer_;

    usable_ = true;
}

const lfs_config *LfsStorage::config() const
{
    return usable_ ? &config_ : nullptr;
}

int LfsStorage::read_block(const lfs_config *c, lfs_block_t block,
                           lfs_off_t off, void *buffer, lfs_size_t size)
{
    LfsStorage *self = static_cast<LfsStorage *>(c->context);
    const uint32_t at = block * c->block_size + off;
    return self->dev_.read(at, buffer, size) ? 0 : LFS_ERR_IO;
}

int LfsStorage::prog_block(const lfs_config *c, lfs_block_t block,
                           lfs_off_t off, const void *buffer, lfs_size_t size)
{
    LfsStorage *self = static_cast<LfsStorage *>(c->context);
    const uint32_t at = block * c->block_size + off;
    return self->dev_.program(at, buffer, size) ? 0 : LFS_ERR_IO;
}

int LfsStorage::erase_block(const lfs_config *c, lfs_block_t block)
{
    LfsStorage *self = static_cast<LfsStorage *>(c->context);
    const uint32_t at = block * c->block_size;
    return self->dev_.erase(at, c->block_size) ? 0 : LFS_ERR_IO;
}

int LfsStorage::sync_device(const lfs_config *c)
{
    /* Nothing is buffered below this: a program has reached the chip by the
       time it returns. */
    (void)c;
    return 0;
}

LfsFileBuffer::LfsFileBuffer()
{
    config_.buffer = buffer_;
    config_.attrs = nullptr;
    config_.attr_count = 0;
}

const lfs_file_config *LfsFileBuffer::config() const
{
    return &config_;
}
