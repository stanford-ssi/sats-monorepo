"""Six-degree-of-freedom rigid-body dynamics."""

from unittest.mock import patch

import numpy as np

from arda.common.rotations import Quaternion
from arda.physics.dynamics.gravity import gravity_force_moment
from arda.types import ForceMoment, Satellite, State, StateDerivative


def derivative(
    _time_s: float,
    state: State,
    satellite: Satellite,
) -> StateDerivative:
    # Get force in ECI and moment in body coordinates.
    force_moment = gravity_force_moment(state, satellite)

    # Get angular velocity and attitude derivative in ECI.
    angular_velocity_body_wrt_eci_eci_rad_per_s = (
        state.angular_velocity_body_wrt_eci_eci_rad_per_s
    )
    quat_dot_eci_to_body_per_s = state.quat_eci_to_body.derivative(
        angular_velocity_body_wrt_eci_eci_rad_per_s
    )

    # Rotate into body coordinates, since satellite inertia is constant there.
    dcm_eci_to_body = state.quat_eci_to_body.as_dcm()
    angular_velocity_body_wrt_eci_body_rad_per_s = (
        dcm_eci_to_body @ angular_velocity_body_wrt_eci_eci_rad_per_s
    )
    # Euler rigid body `w_dot = J^-1(tau - w × (Jw)).`
    angular_acceleration_body_wrt_eci_body_rad_per_s2 = np.linalg.solve(
        satellite.inertia_body_kgm2,
        force_moment.moment_body_nm
        - np.cross(
            angular_velocity_body_wrt_eci_body_rad_per_s,
            satellite.inertia_body_kgm2 @ angular_velocity_body_wrt_eci_body_rad_per_s,
        ),
    )

    # Resolve angular acceleration in ECI.
    angular_acceleration_body_wrt_eci_eci_rad_per_s2 = (
        dcm_eci_to_body.T @ angular_acceleration_body_wrt_eci_body_rad_per_s2
    )
    return StateDerivative(
        velocity_eci_m_per_s=state.velocity_eci_m_per_s,
        acceleration_eci_m_per_s2=force_moment.force_eci_n / satellite.mass_kg,
        quat_dot_eci_to_body_per_s=quat_dot_eci_to_body_per_s,
        angular_acceleration_body_wrt_eci_eci_rad_per_s2=(
            angular_acceleration_body_wrt_eci_eci_rad_per_s2
        ),
    )


def test_passive_attitude_derivative_uses_eci_rate() -> None:
    state = State(
        position_eci_m=np.array([7_000_000.0, 0.0, 0.0]),
        velocity_eci_m_per_s=np.zeros(3),
        quat_eci_to_body=Quaternion.identity(),
        angular_velocity_body_wrt_eci_eci_rad_per_s=np.array([0.0, 0.0, 1.0]),
    )
    result = derivative(0.0, state, Satellite(1.0, np.eye(3)))

    np.testing.assert_allclose(
        result.quat_dot_eci_to_body_per_s,
        [0.0, 0.0, -0.5, 0.0],
    )


def test_derivative_uses_body_frame_moment() -> None:
    state = State(
        position_eci_m=np.array([7_000_000.0, 0.0, 0.0]),
        velocity_eci_m_per_s=np.zeros(3),
        quat_eci_to_body=Quaternion.from_axis_angle(
            np.array([0.0, 0.0, 1.0]), np.pi / 2.0
        ),
        angular_velocity_body_wrt_eci_eci_rad_per_s=np.zeros(3),
    )
    force_moment = ForceMoment(
        force_eci_n=np.zeros(3),
        moment_body_nm=np.array([1.0, 2.0, 3.0]),
    )

    with patch(
        "arda.physics.rigid_body.gravity_force_moment", return_value=force_moment
    ):
        result = derivative(0.0, state, Satellite(1.0, np.eye(3)))

    np.testing.assert_allclose(
        result.angular_acceleration_body_wrt_eci_eci_rad_per_s2,
        [-2.0, 1.0, 3.0],
        atol=1e-12,
    )
