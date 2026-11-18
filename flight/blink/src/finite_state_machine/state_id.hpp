#pragma once
/**
 * Enum class for every state IDs in the Finite State Machine.
 * Author: Saish Swamidurai
 * Date: 7 November 2026
 */
enum class state_id
{
    init,
    bringup,
    burn_wire,
    burn_wire_reset,
    running,
    count
};
