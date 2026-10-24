"""Two-body gravity force and gravity-gradient moment."""

import numpy as np

from arda.common.rotations import Quaternion
from arda.constants import EARTH_GRAVITATIONAL_PARAMETER_M3_PER_S2
from arda.types import FloatArray, ForceMoment, Satellite, State


def gravity_force_moment(
    state: State,
    satellite: Satellite,
) -> ForceMoment:
    return ForceMoment(
        force_eci_n=_gravity_force_eci_n(state.position_eci_m, satellite.mass_kg),
        moment_eci_nm=_gravity_gradient_moment_eci_nm(
            state.position_eci_m,
            state.quat_eci_to_body,
            satellite.inertia_body_kgm2,
        ),
    )


def _gravity_force_eci_n(position_eci_m: FloatArray, mass_kg: float) -> FloatArray:
    radius_m = np.linalg.norm(position_eci_m)
    acceleration_eci_m_per_s2 = (
        -EARTH_GRAVITATIONAL_PARAMETER_M3_PER_S2 * position_eci_m / radius_m**3
    )
    return mass_kg * acceleration_eci_m_per_s2


def _gravity_gradient_moment_eci_nm(
    _position_eci_m: FloatArray,
    _quat_eci_to_body: Quaternion,
    _inertia_body_kgm2: FloatArray,
) -> FloatArray:
    """Return zero until gravity-gradient dynamics are implemented."""
    return np.zeros(3)


def test_gravity_force_moment() -> None:
    state = State(
        position_eci_m=np.array([7_000_000.0, 7_000_000.0, 0.0]),
        velocity_eci_m_per_s=np.zeros(3),
        quat_eci_to_body=Quaternion.identity(),
        angular_velocity_body_wrt_eci_eci_rad_per_s=np.zeros(3),
    )
    satellite = Satellite(10.0, np.diag([1.0, 2.0, 3.0]))

    force_moment = gravity_force_moment(state, satellite)

    assert np.all(force_moment.force_eci_n[:2] < 0.0)
    np.testing.assert_array_equal(force_moment.moment_eci_nm, np.zeros(3))
