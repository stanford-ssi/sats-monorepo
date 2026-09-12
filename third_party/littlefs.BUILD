"""
Build for littlefs, which ships no bazel files of its own.

Only the four files that make up the filesystem are compiled; the emulated
block devices under bd/, the test runners and the benches are left out.
"""

load("@rules_cc//cc:cc_library.bzl", "cc_library")

package(default_visibility = ["//visibility:public"])

cc_library(
    name = "littlefs",
    srcs = [
        "lfs.c",
        "lfs_util.c",
    ],
    hdrs = [
        "lfs.h",
        "lfs_util.h",
    ],
    defines = [
        # No heap. Every buffer littlefs needs is handed to it by
        # common/fs, which is what the rest of this firmware does too.
        "LFS_NO_MALLOC",
        # No printf. The cdc port carries cobs framed commands, so anything
        # littlefs printed would be corruption as far as the ground is
        # concerned; errors come back as return codes instead.
        "LFS_NO_DEBUG",
        "LFS_NO_WARN",
        "LFS_NO_ERROR",
    ],
    includes = ["."],
)

exports_files(["LICENSE.md"])
