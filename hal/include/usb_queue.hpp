#pragma once
/**
 * Author: Carson Lauer
 * Date: 9 September 2026
 */
#include <stdint.h>

#include "common/util/queue.hpp"

class UsbQueue : public Queue<uint8_t>
{
public:
    UsbQueue();

    bool empty() const override;

    bool push(const uint8_t &item) override;

    bool pop(uint8_t &item) override;
};
