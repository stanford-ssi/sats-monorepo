/**
 * Author: Carson Lauer
 * Date: 11 September 2026
 */

#include "common/fs/lfs_files.hpp"

#include "common/fs/lfs_storage.hpp"

int lfs_read_whole(lfs_t *lfs, const char *name, void *dst, uint32_t cap)
{
    LfsFileBuffer buffer{};
    lfs_file_t file;
    int err = lfs_file_opencfg(lfs, &file, name, LFS_O_RDONLY, buffer.config());
    if (err < 0) {
        return err;
    }

    const lfs_ssize_t read = lfs_file_read(lfs, &file, dst, cap);

    /* Closed whatever happened, since a file left open holds a cache and
       a slot in littlefs's list of them. */
    err = lfs_file_close(lfs, &file);
    if (read < 0) {
        return static_cast<int>(read);
    }
    return err < 0 ? err : static_cast<int>(read);
}

int lfs_write_whole(lfs_t *lfs, const char *name, const void *src, uint32_t len)
{
    LfsFileBuffer buffer{};
    lfs_file_t file;
    int err = lfs_file_opencfg(lfs, &file, name,
                               LFS_O_WRONLY | LFS_O_CREAT | LFS_O_TRUNC,
                               buffer.config());
    if (err < 0) {
        return err;
    }

    const lfs_ssize_t written = lfs_file_write(lfs, &file, src, len);

    /* The close is what commits it: until then the new contents are in the
       file's cache, so its error matters as much as the write's. Ignoring
       it is the way a save gets reported as having worked and is not
       there on the next boot. */
    err = lfs_file_close(lfs, &file);
    if (written < 0) {
        return static_cast<int>(written);
    }
    return err < 0 ? err : static_cast<int>(written);
}
