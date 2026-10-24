"""Shared simulator data types."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from arda.common.rotations import Quaternion

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class ForceMoment:
    force_eci_n: FloatArray
    moment_eci_nm: FloatArray

    def __add__(self, other: "ForceMoment") -> "ForceMoment":
        return ForceMoment(
            self.force_eci_n + other.force_eci_n,
            self.moment_eci_nm + other.moment_eci_nm,
        )


@dataclass(frozen=True)
class State:
    position_eci_m: FloatArray
    velocity_eci_m_per_s: FloatArray
    quat_eci_to_body: Quaternion
    angular_velocity_body_wrt_eci_eci_rad_per_s: FloatArray

    def as_array(self) -> FloatArray:
        return np.concatenate(
            (
                self.position_eci_m,
                self.velocity_eci_m_per_s,
                self.quat_eci_to_body.xyzw,
                self.angular_velocity_body_wrt_eci_eci_rad_per_s,
            )
        )

    @classmethod
    def from_array(cls, state: FloatArray) -> "State":
        return cls(state[:3], state[3:6], Quaternion(state[6:10]), state[10:13])


@dataclass(frozen=True)
class StateDerivative:
    position_eci_m_per_s: FloatArray
    velocity_eci_m_per_s2: FloatArray
    quat_dot_eci_to_body_per_s: FloatArray
    angular_acceleration_body_wrt_eci_eci_rad_per_s2: FloatArray

    def as_array(self) -> FloatArray:
        return np.concatenate(
            (
                self.position_eci_m_per_s,
                self.velocity_eci_m_per_s2,
                self.quat_dot_eci_to_body_per_s,
                self.angular_acceleration_body_wrt_eci_eci_rad_per_s2,
            )
        )


@dataclass(frozen=True)
class Satellite:
    mass_kg: float
    inertia_body_kgm2: FloatArray


@dataclass(frozen=True)
class Scenario:
    name: str
    satellite: Satellite
    initial_state: State
    duration_s: float
    step_s: float
