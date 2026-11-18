#pragma once
/**
 * Abstract base class for every state in the Finite State Machine.
 * Author: Saish Swamidurai
 * Date: 7 November 2026
*/
#include "state_id.hpp"
#include <span>
#include <string_view>

class Task;

class State {
public:
    State(const State &) = delete;
    State &operator=(const State &) = delete;

    virtual void on_enter() = 0;
    virtual state_id get_next_state() = 0;

    virtual std::string_view get_name() const = 0;

    state_id get_id() const{
        return id_;
    }

    std::span<Task* const> get_task_list() const{
        return task_list_;
    }

protected:
    State(state_id id, std::span<Task* const> task_list)
        : _id(id), _task_list(task_list) {}
    
    ~State() = default;

private:
    const state_id id_;
    const std::span<Task* const> task_list_; 
};