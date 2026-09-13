"""
Contains the SatelliteState class

@date 2026-09-12

TODO: include checks for valid parameters (e.g. normalized quaternion, 3D vectors, etc)
"""

import numpy as np
from math_utils import Quaternion


class SatelliteState:
    def __init__(
        self,
        q_eci2body: Quaternion,
        omega_eci: np.array,
        r_eci: np.ndarray,
        v_eci: np.ndarray,
        t: float = 0.0,
        mjd_epoch: float = 0.0,
    ):
        self.q_eci2body = q_eci2body  # scalar-last quaternion, ECI to body frame
        self.omega_eci = omega_eci  # angular velocity in ECI frame [rad/s]
        self.r_eci = r_eci  # position in ECI frame [m]
        self.v_eci = v_eci  # velocity in ECI frame [m/s]
        self.t = t  # time [s]
        self.mjd_epoch = mjd_epoch  # time in modified Julian days [days]

    def __repr__(self):
        return (
            f"SatelliteState(t={self.t}, q={self.q}, "
            f"w={self.w}, r={self.r}, v={self.v})"
        )

    def __str__(self):
        return (
            f"SatelliteState(t={self.t}, q={self.q}, "
            f"w={self.w}, r={self.r}, v={self.v})"
        )

    def __add__(self, other):
        return SatelliteState(
            self.q + other.q,
            self.w + other.w,
            self.r + other.r,
            self.v + other.v,
            self.t,
        )

    def __sub__(self, other):
        return SatelliteState(
            self.q - other.q,
            self.w - other.w,
            self.r - other.r,
            self.v - other.v,
            self.t,
        )

    def __mul__(self, scalar):
        return SatelliteState(
            self.q * scalar,
            self.w * scalar,
            self.r * scalar,
            self.v * scalar,
            self.t * scalar,
            self.mjd_epoch,
        )

    def __truediv__(self, scalar):
        return SatelliteState(
            self.q / scalar,
            self.w / scalar,
            self.r / scalar,
            self.v / scalar,
            self.t / scalar,
            self.mjd_epoch,
        )

    def __rmul__(self, scalar):
        return self.__mul__(scalar)

    def __rtruediv__(self, scalar):
        return self.__truediv__(scalar)
