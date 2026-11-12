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
        moment_body_nm=_gravity_gradient_moment_body_nm(
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


def _gravity_gradient_moment_body_nm(
    position_eci_m: FloatArray,
    quat_eci_to_body: Quaternion,
    inertia_body_kgm2: FloatArray,
) -> FloatArray:
    # Return 3 mu / r^3 * (n x I n)
    # n the unit radial vector in body frame
    # I = inertia of the satellite in body frame
    radius_m = np.linalg.norm(position_eci_m)
    radial_unit_body = quat_eci_to_body.as_dcm() @ (position_eci_m / radius_m)
    return (
        3.0
        * EARTH_GRAVITATIONAL_PARAMETER_M3_PER_S2
        / radius_m**3
        * np.cross(radial_unit_body, inertia_body_kgm2 @ radial_unit_body)
    )


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
    # n = [1, 1, 0] / sqrt(2), so n x I n = [0, 0, (I_yy - I_xx) / 2].
    radius_m = np.linalg.norm(state.position_eci_m)
    expected_moment_body_nm = (
        3.0
        * EARTH_GRAVITATIONAL_PARAMETER_M3_PER_S2
        / radius_m**3
        * np.array([0.0, 0.0, 0.5])
    )
    np.testing.assert_allclose(force_moment.moment_body_nm, expected_moment_body_nm)


"""Check that gravity_gradient torque vanishes 
    when satellite is aligned with a principal axis."""


def test_gravity_gradient_moment_vanishes_on_principal_axis() -> None:
    moment_body_nm = _gravity_gradient_moment_body_nm(
        np.array([7_000_000.0, 0.0, 0.0]),
        Quaternion.identity(),
        np.diag([3.0, 2.0, 1.0]),
    )
    np.testing.assert_allclose(moment_body_nm, np.zeros(3), atol=1e-20)
