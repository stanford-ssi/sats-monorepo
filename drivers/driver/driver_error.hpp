#pragma once
/**
 * A driver error; used with std::expected.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <stdint.h>

enum class DriverError : uint8_t
{
    NotReady,   /* init() did not succeed */
    Busy,       /* the driver is currently busy */
    InvalidArg, /* an invalid argument was provided */
    HwFault,    /* a fault occured on the hardware */
};
