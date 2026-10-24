"""Integration methods."""

from collections.abc import Callable

from arda.types import FloatArray


def rk4_step(
    state_derivative: Callable[[float, FloatArray], FloatArray],
    time_s: float,
    state: FloatArray,
    step_s: float,
) -> FloatArray:
    k1 = state_derivative(time_s, state)
    k2 = state_derivative(time_s + step_s / 2, state + step_s * k1 / 2)
    k3 = state_derivative(time_s + step_s / 2, state + step_s * k2 / 2)
    k4 = state_derivative(time_s + step_s, state + step_s * k3)
    return state + step_s * (k1 + 2 * k2 + 2 * k3 + k4) / 6
