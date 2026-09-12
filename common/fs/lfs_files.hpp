#pragma once
/**
 * Author: Carson Lauer
 * Date: 11 September 2026
 */

#include <stdint.h>

#include "lfs.h"

/**
 * Whole file reads and writes, which littlefs has no single call for.
 *
 * Everything this firmware keeps in flash is a whole value: a settings
 * struct read once at startup and written back when the ground asks for
 * it. Through littlefs directly that is an open, an operation and a close,
 * and the close is the one that commits, so all three return codes matter.
 * They are collapsed here rather than in every app, because an app that
 * checks the write and not the close loses saves without ever saying so.
 *
 * Nothing else is wrapped. littlefs's own api is the way to do anything
 * with directories, seeking, appending or attributes, and its docs are the
 * reference for what it does; these two are here to stop the same dozen
 * lines being written again in every app.
 *
 * Both put an LfsFileBuffer on the stack, a cache page plus change. A
 * caller on a tight stack, or one holding a file open across calls, wants
 * lfs_file_opencfg() and its own buffer instead.
 */

/**
 * Read up to `cap` bytes of `name` into `dst`.
 *
 * Returns the byte count, or a negative LFS_ERR. A file longer than `cap`
 * is not an error and comes back truncated, so a caller expecting a fixed
 * size struct should compare the count against sizeof it.
 */
int lfs_read_whole(lfs_t *lfs, const char *name, void *dst, uint32_t cap);

/**
 * Replace the contents of `name` with `len` bytes of `src`, creating the
 * file if it is not there. Returns the byte count, or a negative LFS_ERR.
 */
int lfs_write_whole(lfs_t *lfs, const char *name, const void *src,
                    uint32_t len);
