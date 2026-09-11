#pragma once

template <typename T>
class Queue {
public:
    virtual bool push(const T& item) = 0;

    virtual bool pop(T& item) = 0;

    virtual bool empty() const = 0;
};
