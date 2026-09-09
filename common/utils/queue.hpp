#pragma once

template <typename T>
class Queue {
public:
    Queue() {}

    virtual bool push(const T& item) {
        return true;
    }

    virtual bool pop(T& item) {
        return true;
    }

    virtual bool empty() const {
        return true;
    }
};
