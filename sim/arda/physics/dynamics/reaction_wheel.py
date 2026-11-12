"""Reaction wheel torque with a first-order wheel speed response."""

from dataclasses import dataclass

import numpy as np

from arda.common.rotations import Quaternion
from arda.types import FloatArray, ForceMoment, Satellite, State


@dataclass(frozen=True)
class ReactionWheel:
    """Reaction wheel mounted on the satellite.

    `spin_axis_body` is the wheel spin axis in body coordinates.
    `position_body_m` is the mounting location relative to the satellite center of
    mass.

    Location does NOT matter for this calculation, so can be discarded if desired.
    """

    spin_axis_body: FloatArray
    position_body_m: FloatArray
    spin_inertia_kgm2: float
    time_constant_s: float

    def __post_init__(self) -> None:
        axis = np.array(self.spin_axis_body, dtype=np.float64, copy=True)
        if axis.shape != (3,) or np.linalg.norm(axis) == 0.0:
            raise ValueError("spin axis must be a nonzero shape-(3,) array")
        if self.time_constant_s <= 0.0:
            raise ValueError("time constant must be positive")
        object.__setattr__(self, "spin_axis_body", axis / np.linalg.norm(axis))


def wheel_angular_acceleration_rad_per_s2(
    wheel_speed_rad_per_s: float,
    target_wheel_speed_rad_per_s: float,
    time_constant_s: float,
) -> float:
    """First-order lag `Ω_dot = (Ω_target - Ω) / τ` of wheel speed relative to body."""
    return (target_wheel_speed_rad_per_s - wheel_speed_rad_per_s) / time_constant_s


def reaction_wheel_force_moment(
    state: State,
    wheel: ReactionWheel,
    wheel_speed_rad_per_s: float,
    target_wheel_speed_rad_per_s: float,
) -> ForceMoment:
    """Return the wheel moment on the satellite in body coordinates.

    Here the convention is the satellite inertia J includes the wheel.

    From Markley, Euler's equation for this form of J is given by:
    tau = J w_dot + w x (J + H_w) + H_w_dot

    tau is the moment on the wheel
    J is the inertia of the WHOLE satellite (including the wheels)
    H_w is the angular momentum of the wheels along their spin axis
    w = angular velocity vector as normal

    The resulting effective torque on the body is given by
    tau_wheel_on_body = -H_w_dot - w x H_w
    """
    wheel_acceleration_rad_per_s2 = wheel_angular_acceleration_rad_per_s2(
        wheel_speed_rad_per_s, target_wheel_speed_rad_per_s, wheel.time_constant_s
    )
    angular_velocity_body_wrt_eci_body_rad_per_s = (
        state.quat_eci_to_body.as_dcm()
        @ state.angular_velocity_body_wrt_eci_eci_rad_per_s
    )
    wheel_momentum_body_nms = (
        wheel.spin_inertia_kgm2 * wheel_speed_rad_per_s * wheel.spin_axis_body
    )
    wheel_momentum_dot_body_nm = (
        wheel.spin_inertia_kgm2 * wheel_acceleration_rad_per_s2 * wheel.spin_axis_body
    )
    return ForceMoment(
        force_eci_n=np.zeros(3),
        moment_body_nm=-wheel_momentum_dot_body_nm
        - np.cross(
            angular_velocity_body_wrt_eci_body_rad_per_s, wheel_momentum_body_nms
        ),
    )


# testing


def _state(
    quat_eci_to_body: Quaternion, angular_velocity_eci_rad_per_s: FloatArray
) -> State:
    return State(
        position_eci_m=np.array([7_000_000.0, 0.0, 0.0]),
        velocity_eci_m_per_s=np.array([0.0, 7_500.0, 0.0]),
        quat_eci_to_body=quat_eci_to_body,
        angular_velocity_body_wrt_eci_eci_rad_per_s=angular_velocity_eci_rad_per_s,
    )


def test_wheel_angular_acceleration_is_first_order_lag() -> None:
    assert wheel_angular_acceleration_rad_per_s2(100.0, 300.0, 0.5) == 400.0
    assert wheel_angular_acceleration_rad_per_s2(300.0, 300.0, 0.5) == 0.0


def test_wheel_spin_up_reacts_on_body() -> None:
    wheel = ReactionWheel(
        np.array([0.0, 0.0, 2.0]), np.array([0.1, 0.0, 0.0]), 1e-3, 0.5
    )
    state = _state(Quaternion.identity(), np.zeros(3))

    moment_body_nm = reaction_wheel_force_moment(
        state, wheel, 100.0, 300.0
    ).moment_body_nm

    np.testing.assert_allclose(moment_body_nm, [0.0, 0.0, -0.4])


def test_spinning_wheel_adds_gyroscopic_moment() -> None:
    wheel = ReactionWheel(np.array([0.0, 0.0, 1.0]), np.zeros(3), 1e-3, 0.5)
    state = _state(Quaternion.identity(), np.array([1.0, 0.0, 0.0]))

    moment_body_nm = reaction_wheel_force_moment(
        state, wheel, 100.0, 100.0
    ).moment_body_nm

    # -w × h = -[1, 0, 0] × [0, 0, 0.1] = [0, 0.1, 0]
    np.testing.assert_allclose(moment_body_nm, [0.0, 0.1, 0.0])


def test_wheel_moment_matches_angular_acceleration() -> None:
    inertia_body_kgm2 = np.diag([1.0, 2.0, 3.0])
    satellite = Satellite(10.0, inertia_body_kgm2)
    wheel = ReactionWheel(np.array([0.0, 0.0, 1.0]), np.zeros(3), 1e-3, 0.5)
    state = _state(Quaternion.identity(), np.zeros(3))

    moment_body_nm = reaction_wheel_force_moment(
        state, wheel, 100.0, 300.0
    ).moment_body_nm

    np.testing.assert_allclose(
        np.linalg.solve(satellite.inertia_body_kgm2, moment_body_nm),
        [0.0, 0.0, -0.4 / 3.0],
    )
