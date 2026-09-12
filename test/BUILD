package(default_visibility = ["//visibility:public"])

cc_test(
    name = "example_test",
    size = "small",
    srcs = ["example_test.cpp"],
    deps = [
        "@googletest//:gtest",
        "@googletest//:gtest_main",
    ],
)

cc_test(
    name = "cmd_receiver_test",
    size = "small",
    srcs = ["cmd_receiver_test.cpp"],
    deps = [
        "//common/cmd_receiver",
        "//common/cobs",
        "//common/util",
        "//proto:sats_command_nanopb",
        "@googletest//:gtest",
        "@googletest//:gtest_main",
    ],
)

cc_test(
    name = "cmd_responder_test",
    size = "small",
    srcs = ["cmd_responder_test.cpp"],
    deps = [
        "//common/cmd_responder",
        "//common/cobs",
        "//common/util",
        "//proto:sats_command_nanopb",
        "@googletest//:gtest",
        "@googletest//:gtest_main",
    ],
)

cc_test(
    name = "interval_test",
    size = "small",
    srcs = ["interval_test.cpp"],
    deps = [
        "//common/util",
        "@googletest//:gtest",
        "@googletest//:gtest_main",
    ],
)

cc_test(
    name = "fs_test",
    size = "small",
    srcs = ["fs_test.cpp"],
    deps = [
        "//common/fs",
        "//common/fs:ram_block_device",
        "@googletest//:gtest",
        "@googletest//:gtest_main",
    ],
)
