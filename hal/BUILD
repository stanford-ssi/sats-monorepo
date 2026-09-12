package(default_visibility = ["//visibility:public"])

cc_library(
    name = "pico_hal",
    hdrs = [
        "include/flash.hpp",
        "include/usb_queue.hpp",
    ],
    srcs = [
        "pico/flash.cpp",
        "pico/usb_queue.cpp",
    ],
    deps = [
        "//common/fs",
        "//common/util",
        "@pico-sdk//src/rp2_common/hardware_flash",
        "@pico-sdk//src/rp2_common/hardware_sync",
        "@pico-sdk//src/rp2_common/pico_stdlib",
        "@pico-sdk//src/rp2_common/pico_stdio_usb",
    ],
    strip_include_prefix = "/hal/include",
    include_prefix = "hal",
    target_compatible_with = ["//platforms:arm_cortex_m33"],
)
