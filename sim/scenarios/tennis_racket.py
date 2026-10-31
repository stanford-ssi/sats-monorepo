"""Satellite undergoing Dzhanibekov 'tennis racket' effect"""

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
        name="tennis racket",
        satellite=Satellite(
            mass_kg=2.0,
            inertia_body_kgm2=np.diag([0.3, 0.2, 0.15]),
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
            angular_velocity_body_wrt_eci_eci_rad_per_s=np.array([0.01, 1.0, 0.0]),
        ),
        duration_s=60.0,
        step_s=0.10,
    )
