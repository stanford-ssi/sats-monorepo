package(default_visibility = ["//visibility:public"])

cc_library(
    name = "pico_hal",
    hdrs = [
        "include/usb_queue.hpp",
        "include/gpio.hpp",
    ],
    srcs = ["pico/usb_queue.cpp"],
    deps = [
        "//hal:pico_hal_hardware",
        "//common/util",
        "@pico-sdk//src/rp2_common/pico_stdlib",
        "@pico-sdk//src/rp2_common/pico_stdio_usb",
    ],
    strip_include_prefix = "/hal/include",
    include_prefix = "hal",
    target_compatible_with = ["//platforms:arm_cortex_m33"],
)

cc_library(
    name = "pico_hal_hardware",
    hdrs = ["pico/pico_gpio.hpp"],
     deps = [
        "//common/util",
        "@pico-sdk//src/rp2_common/pico_stdlib",
        "@pico-sdk//src/rp2_common/pico_stdio_usb",
    ],
    target_compatible_with = ["//platforms:arm_cortex_m33"],
)
