#pragma once
/**
 * Compile-time check that a board uses each pin (or bus address) once.
 * Author: Ayush Garg
 * Date: 31 October 2026
 */

#include <array>
#include <cstddef>

/**
 * Checks if all entries in an array are unique.
 */
template <typename T, std::size_t N>
constexpr bool all_unique(const std::array<T, N> &values)
{
    for (std::size_t i = 0; i < N; i++) {
        for (std::size_t j = i + 1; j < N; j++) {
            if (values[i] == values[j]) {
                return false;
            }
        }
    }
    return true;
}
