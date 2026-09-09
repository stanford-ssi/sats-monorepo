// ring_buffer.hpp
#pragma once

#include <array>
#include <cstdint>
#include <cstddef>
#include <type_traits>

#include "queue.hpp"

template <typename T, std::size_t Size>
class RingBuffer : public Queue<T> {
    static_assert((Size & (Size - 1)) == 0, "Size must be a power of 2");
    static_assert(Size > 0, "Size must be non-zero");

public:
    RingBuffer() : head_(0), tail_(0) {}

    bool empty() const {
        return head_ == tail_;
    }

    bool full() const {
        return next(head_) == tail_;
    }

    // Returns false if the buffer was full (item dropped)
    bool push(const T& item) {
        std::size_t next_head = next(head_);
        if (next_head == tail_) {
            return false;  // full
        }
        buf_[head_] = item;
        head_ = next_head;
        return true;
    }

    // Returns false if the buffer was empty
    bool pop(T& item) {
        if (head_ == tail_) {
            return false;  // empty
        }
        item = buf_[tail_];
        tail_ = next(tail_);
        return true;
    }

    std::size_t count() const {
        return (head_ - tail_) & (Size - 1);
    }

    static constexpr std::size_t capacity() {
        return Size - 1;  // one slot reserved to disambiguate full/empty
    }

    void clear() {
        head_ = tail_ = 0;
    }

private:
    static std::size_t next(std::size_t idx) {
        return (idx + 1) & (Size - 1);
    }

    std::array<T, Size> buf_;
    volatile std::size_t head_;  // next write index
    volatile std::size_t tail_;  // next read index
};

