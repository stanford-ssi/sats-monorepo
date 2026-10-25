"""Simulation loop."""

import numpy as np
from tqdm import tqdm

from arda.common.integrators import rk4_step
from arda.physics.rigid_body import derivative
from arda.telemetry import Telemetry, capture_returns
from arda.types import FloatArray, Scenario, State


def run(scenario: Scenario, *, progress: bool = False) -> Telemetry:
    def state_derivative(time_s: float, state: FloatArray) -> FloatArray:
        simulation_state = State.from_array(state)
        return derivative(
            time_s,
            simulation_state,
            scenario.satellite,
        ).as_array()

    time_s = np.arange(0.0, scenario.duration_s + scenario.step_s, scenario.step_s)
    states = np.empty((time_s.size, 13))
    states[0] = scenario.initial_state.as_array()
    steps = tqdm(
        time_s[:-1],
        desc=scenario.name,
        unit="step",
        disable=not progress,
    )
    for index, time in enumerate(steps):
        states[index + 1] = rk4_step(
            state_derivative, time, states[index], scenario.step_s
        )
        states[index + 1, 6:10] /= np.linalg.norm(states[index + 1, 6:10])

    samples = []
    for time, state_array in zip(time_s, states, strict=True):
        state = State.from_array(state_array)
        with capture_returns() as model_outputs:
            derivative(time, state, scenario.satellite)
        samples.append({"state": state, **model_outputs})
    return Telemetry.from_samples(time_s, samples)
