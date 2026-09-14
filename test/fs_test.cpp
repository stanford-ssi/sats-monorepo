/**
 * Tests for the littlefs wiring in common/fs.
 *
 * littlefs comes with its own test suite, so none of this is trying to test
 * the filesystem. What is checked here is that the block device underneath
 * it is addressed the way it expects: that reads and programs land at the
 * offset a block and an offset add up to, that the geometry handed over
 * describes the device it is actually talking to, and that a file therefore
 * survives being unmounted and mounted again.
 */
#include <gtest/gtest.h>

#include <cstdint>
#include <string>

#include "lfs.h"

#include "common/fs/lfs_files.hpp"
#include "common/fs/lfs_storage.hpp"
#include "common/fs/ram_block_device.hpp"

namespace
{

/* 32 blocks of the rp2350's 4 KiB, the region the board gives over. */
constexpr uint32_t kRegionSize = 128 * 1024;

/* Thin std::string wrappers over the library's whole file calls, so these
   tests cover the code the apps actually use rather than a second copy of
   it. */
int write_whole(lfs_t *lfs, const char *name, const std::string &value)
{
    return lfs_write_whole(lfs, name, value.data(),
                           static_cast<uint32_t>(value.size()));
}

/* The contents, or "" with `err_out` set to what littlefs said. */
std::string read_whole(lfs_t *lfs, const char *name, int *err_out = nullptr)
{
    char bytes[16 * 1024]{};
    const int read = lfs_read_whole(lfs, name, bytes, sizeof(bytes));
    if (err_out != nullptr) {
        *err_out = read;
    }
    if (read < 0) {
        return {};
    }
    return std::string(bytes, static_cast<size_t>(read));
}

TEST(FsTest, FormatsAndMountsABlankDevice)
{
    RamBlockDevice flash{kRegionSize};
    LfsStorage device{flash};
    ASSERT_NE(device.config(), nullptr);

    lfs_t lfs{};
    ASSERT_EQ(lfs_format(&lfs, device.config()), 0);
    ASSERT_EQ(lfs_mount(&lfs, device.config()), 0);
    EXPECT_EQ(lfs_unmount(&lfs), 0);
}

TEST(FsTest, MountingABlankDeviceFailsRatherThanInventingAFilesystem)
{
    RamBlockDevice flash{kRegionSize};
    LfsStorage device{flash};

    lfs_t lfs{};
    EXPECT_LT(lfs_mount(&lfs, device.config()), 0);
}

TEST(FsTest, AFileSurvivesARemount)
{
    RamBlockDevice flash{kRegionSize};
    LfsStorage device{flash};

    {
        lfs_t lfs{};
        ASSERT_EQ(lfs_format(&lfs, device.config()), 0);
        ASSERT_EQ(lfs_mount(&lfs, device.config()), 0);
        ASSERT_EQ(write_whole(&lfs, "settings", "sleep_ms=1000"), 13);
        ASSERT_EQ(lfs_unmount(&lfs), 0);
    }

    /* A second mount over the same chip is what a power cycle looks like,
       and it has to read the file back out of flash rather than out of
       anything left in ram. */
    lfs_t lfs{};
    ASSERT_EQ(lfs_mount(&lfs, device.config()), 0);
    EXPECT_EQ(read_whole(&lfs, "settings"), "sleep_ms=1000");
    EXPECT_EQ(lfs_unmount(&lfs), 0);
}

TEST(FsTest, AFileBiggerThanABlockSurvivesARemount)
{
    RamBlockDevice flash{kRegionSize};
    LfsStorage device{flash};

    /* Spanning several blocks and not a repeating pattern, so a block
       addressed wrongly cannot read back as the right bytes anyway. */
    std::string big(10000, '\0');
    for (size_t i = 0; i < big.size(); i++) {
        big[i] = static_cast<char>((i * 31 + 7) & 0xFF);
    }

    lfs_t lfs{};
    ASSERT_EQ(lfs_format(&lfs, device.config()), 0);
    ASSERT_EQ(lfs_mount(&lfs, device.config()), 0);
    ASSERT_EQ(write_whole(&lfs, "blob", big), static_cast<int>(big.size()));
    ASSERT_EQ(lfs_unmount(&lfs), 0);

    ASSERT_EQ(lfs_mount(&lfs, device.config()), 0);
    EXPECT_EQ(read_whole(&lfs, "blob"), big);
    EXPECT_EQ(lfs_unmount(&lfs), 0);
}

TEST(FsTest, RewritingAFileReplacesIt)
{
    RamBlockDevice flash{kRegionSize};
    LfsStorage device{flash};

    lfs_t lfs{};
    ASSERT_EQ(lfs_format(&lfs, device.config()), 0);
    ASSERT_EQ(lfs_mount(&lfs, device.config()), 0);

    ASSERT_EQ(write_whole(&lfs, "rate", "250"), 3);
    ASSERT_EQ(write_whole(&lfs, "rate", "1000"), 4);
    EXPECT_EQ(read_whole(&lfs, "rate"), "1000");

    ASSERT_EQ(lfs_unmount(&lfs), 0);
    ASSERT_EQ(lfs_mount(&lfs, device.config()), 0);
    EXPECT_EQ(read_whole(&lfs, "rate"), "1000");
    EXPECT_EQ(lfs_unmount(&lfs), 0);
}

TEST(FsTest, RemovesFiles)
{
    RamBlockDevice flash{kRegionSize};
    LfsStorage device{flash};

    lfs_t lfs{};
    ASSERT_EQ(lfs_format(&lfs, device.config()), 0);
    ASSERT_EQ(lfs_mount(&lfs, device.config()), 0);
    ASSERT_EQ(write_whole(&lfs, "doomed", "value"), 5);

    ASSERT_EQ(lfs_remove(&lfs, "doomed"), 0);

    int err = 0;
    read_whole(&lfs, "doomed", &err);
    EXPECT_EQ(err, LFS_ERR_NOENT);
    EXPECT_EQ(lfs_unmount(&lfs), 0);
}

TEST(FsTest, ListsTheRootDirectory)
{
    RamBlockDevice flash{kRegionSize};
    LfsStorage device{flash};

    lfs_t lfs{};
    ASSERT_EQ(lfs_format(&lfs, device.config()), 0);
    ASSERT_EQ(lfs_mount(&lfs, device.config()), 0);
    ASSERT_EQ(write_whole(&lfs, "alpha", "aa"), 2);
    ASSERT_EQ(write_whole(&lfs, "beta", "bbbb"), 4);

    lfs_dir_t dir;
    ASSERT_EQ(lfs_dir_open(&lfs, &dir, "/"), 0);

    uint32_t files = 0;
    uint32_t bytes = 0;
    lfs_info info{};
    while (lfs_dir_read(&lfs, &dir, &info) > 0) {
        if (info.type == LFS_TYPE_REG) {
            files++;
            bytes += info.size;
        }
    }
    EXPECT_EQ(lfs_dir_close(&lfs, &dir), 0);

    EXPECT_EQ(files, 2u);
    EXPECT_EQ(bytes, 6u);
    EXPECT_EQ(lfs_unmount(&lfs), 0);
}

TEST(FsTest, TheRegionIsAsBigAsTheDeviceSays)
{
    RamBlockDevice flash{kRegionSize};
    LfsStorage device{flash};

    lfs_t lfs{};
    ASSERT_EQ(lfs_format(&lfs, device.config()), 0);
    ASSERT_EQ(lfs_mount(&lfs, device.config()), 0);

    /* Filling it up is the check that block_count describes the whole
       device and nothing past it: a count that was too small would run out
       almost immediately, and one that was too large would fail on a read
       or a program off the end rather than with no space. */
    const std::string kilobyte(1024, 'x');
    uint32_t files = 0;
    int err = 0;
    for (uint32_t i = 0; i < 1000; i++) {
        const std::string name = "f" + std::to_string(i);
        err = write_whole(&lfs, name.c_str(), kilobyte);
        if (err < 0) {
            break;
        }
        files++;
    }
    EXPECT_EQ(err, LFS_ERR_NOSPC);

    /* Counted in blocks rather than bytes, because a file too big to live
       in its metadata gets a block to itself however little of it it uses.
       So the fit is against the block count, and a count that was wrong
       would land nowhere near it: half of them would be far too few, and
       more than all of them means the device was addressed past its end. */
    const uint32_t blocks = kRegionSize / 4096;
    EXPECT_GT(files, blocks / 2);
    EXPECT_LT(files, blocks);

    /* And it is still a filesystem afterwards. */
    EXPECT_EQ(read_whole(&lfs, "f0"), kilobyte);
    EXPECT_EQ(lfs_unmount(&lfs), 0);
}

TEST(FsTest, WorksOnOtherGeometries)
{
    struct Shape
    {
        uint32_t size;
        uint32_t erase_size;
        uint32_t program_size;
    };

    const Shape shapes[] = {
        {64 * 1024, 4096, 256},  // the smallest region worth giving over
        {512 * 1024, 4096, 256}, // a more generous one
        {64 * 1024, 4096, 64},   // pages much smaller than a block
        {32 * 1024, 2048, 256},  // and a chip with smaller blocks
    };

    for (const Shape &shape : shapes) {
        RamBlockDevice flash{shape.size, shape.erase_size, shape.program_size};
        LfsStorage device{flash};
        ASSERT_NE(device.config(), nullptr) << shape.size;

        lfs_t lfs{};
        ASSERT_EQ(lfs_format(&lfs, device.config()), 0) << shape.size;
        ASSERT_EQ(lfs_mount(&lfs, device.config()), 0) << shape.size;
        ASSERT_EQ(write_whole(&lfs, "settings", "value"), 5) << shape.size;
        ASSERT_EQ(lfs_unmount(&lfs), 0) << shape.size;

        ASSERT_EQ(lfs_mount(&lfs, device.config()), 0) << shape.size;
        EXPECT_EQ(read_whole(&lfs, "settings"), "value") << shape.size;
        EXPECT_EQ(lfs_unmount(&lfs), 0) << shape.size;
    }
}

TEST(FsTest, RefusesGeometriesItCannotBeConfiguredFor)
{
    {
        /* Pages larger than the cache this can hold. */
        RamBlockDevice flash{64 * 1024, 4096, 512};
        EXPECT_EQ(LfsStorage{flash}.config(), nullptr);
    }
    {
        /* An erase block that is not a whole number of pages. */
        RamBlockDevice flash{64 * 1024, 3000, 256};
        EXPECT_EQ(LfsStorage{flash}.config(), nullptr);
    }
    {
        /* Too few blocks for littlefs's metadata pair, let alone a file. */
        RamBlockDevice flash{4096, 4096, 256};
        EXPECT_EQ(LfsStorage{flash}.config(), nullptr);
    }
    {
        /* A region the board refused to hand over at all. */
        RamBlockDevice flash{0, 4096, 256};
        EXPECT_EQ(LfsStorage{flash}.config(), nullptr);
    }
}

} // namespace
