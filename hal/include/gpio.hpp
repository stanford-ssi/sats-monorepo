#pragma once
/**
 * Hal abstraction over GPIO
 * Author: Carson Lauer, Ayush Garg
 * Date: 31 October 2026
 */

/*
 * To enforce pins being in/out at compile time, we have two classes.
 * If we have the usecase of switching later, we can modify this architecture
 * to include a switchable pin.
 */

/**
 * A writable pin that can be set HIGH or LOW.
 */
class DigitalOut
{
public:
    DigitalOut() = default;
    DigitalOut(const DigitalOut &) = delete;
    DigitalOut &operator=(const DigitalOut &) = delete;

    virtual void set(bool value) = 0;

protected:
    ~DigitalOut() = default;
};

/**
 * A readable pin that can be read HIGH or LOW.
 */
class DigitalIn
{
public:
    DigitalIn() = default;
    DigitalIn(const DigitalIn &) = delete;
    DigitalIn &operator=(const DigitalIn &) = delete;

    virtual bool read() const = 0;

protected:
    ~DigitalIn() = default;
};
