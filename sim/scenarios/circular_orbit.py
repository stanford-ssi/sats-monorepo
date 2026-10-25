"""Satellite in a circular low Earth orbit."""

import numpy as np

from arda.common.rotations import Quaternion
from arda.constants import (
    EARTH_EQUATORIAL_RADIUS_M,
    EARTH_GRAVITATIONAL_PARAMETER_M3_PER_S2,
)
from arda.types import Satellite, Scenario, State


def make_scenario() -> Scenario:
    orbital_radius_m = EARTH_EQUATORIAL_RADIUS_M + 400_000.0
    return Scenario(
        name="circular orbit",
        satellite=Satellite(
            mass_kg=10.0,
            inertia_body_kgm2=np.diag([0.10, 0.11, 0.12]),
        ),
        initial_state=State(
            position_eci_m=np.array([orbital_radius_m, 0.0, 0.0]),
            velocity_eci_m_per_s=np.array(
                [
                    0.0,
                    np.sqrt(EARTH_GRAVITATIONAL_PARAMETER_M3_PER_S2 / orbital_radius_m),
                    0.0,
                ]
            ),
            quat_eci_to_body=Quaternion.identity(),
            angular_velocity_body_wrt_eci_eci_rad_per_s=np.array([0.01, 0.02, 0.03]),
        ),
        duration_s=5_550.0,
        step_s=2.0,
    )


def test_circular_orbit() -> None:
    from dataclasses import replace

    from arda.simulator import run

    scenario = make_scenario()
    result = run(replace(scenario, duration_s=600.0))

    radius_m = np.linalg.norm(result["state/position_eci_m"], axis=1)
    quaternion_norm = np.linalg.norm(result["state/quat_eci_to_body"], axis=1)
    assert np.ptp(radius_m) < 0.1
    np.testing.assert_allclose(quaternion_norm, 1.0, atol=1e-12)

    expected_channels = {
        "state/position_eci_m",
        "state/velocity_eci_m_per_s",
        "state/quat_eci_to_body",
        "state/angular_velocity_body_wrt_eci_eci_rad_per_s",
        "physics/dynamics/gravity/gravity_force_moment/force_eci_n",
        "physics/dynamics/gravity/gravity_force_moment/moment_body_nm",
        "physics/rigid_body/derivative/acceleration_eci_m_per_s2",
    }
    assert expected_channels <= result.channels.keys()
    np.testing.assert_allclose(
        result["physics/dynamics/gravity/gravity_force_moment/force_eci_n"],
        result["physics/rigid_body/derivative/acceleration_eci_m_per_s2"]
        * scenario.satellite.mass_kg,
    )
    assert all(
        not any(segment.startswith("_") for segment in path.split("/"))
        for path in result.channels
    )
