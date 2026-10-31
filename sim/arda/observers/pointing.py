"""Directions to objects"""

from dataclasses import dataclass

import numpy as np

from arda.types import FloatArray, State


@dataclass(frozen=True)
class TargetDirection:
    direction_to_target_eci: FloatArray
    direction_to_target_body: FloatArray
    range_to_target_m: float


def target_direction(
    state: State, target_position_eci_m: FloatArray
) -> TargetDirection:
    dist_eci_m = target_position_eci_m - state.position_eci_m
    range_m = float(np.linalg.norm(dist_eci_m))
    direction_eci = dist_eci_m / range_m
    return TargetDirection(
        direction_to_target_eci=direction_eci,
        direction_to_target_body=state.quat_eci_to_body.as_dcm() @ direction_eci,
        range_to_target_m=range_m,
    )


@dataclass(frozen=True)
class TargetDirectionObserver:
    name: str
    target_position_eci_m: FloatArray

    def measure(self, _time_s: float, state: State) -> TargetDirection:
        return target_direction(state, self.target_position_eci_m)
