import numpy as np
import pymsis

# Default NRLMSISE-00 inputs
DEFAULT_LAT = 37.4275  # north positive     (Position at Stanford)
DEFAULT_LON = -122.1697  # east positive
DEFAULT_TIME = np.datetime64("2026-03-20T14:09")  # (Dawn at Stanford)
# Moderate solar activity
DEFAULT_F107 = 150.0  # daily F10.7 solar flux (sfu)
DEFAULT_F107A = 150.0  # 81-day average F10.7 (sfu)
DEFAULT_AP = 4.0  # daily geomagnetic Ap index


def drag(
    altitude,
    velocity,
    ram_area,
    COP,
    COM,
    cd=2.2,
    lat=DEFAULT_LAT,
    lon=DEFAULT_LON,
    time=DEFAULT_TIME,
    f107=DEFAULT_F107,
    f107a=DEFAULT_F107A,
    ap=DEFAULT_AP,
):
    """
    Compute the aerodynamic drag force and torque on a satellite.

    Inputs
    altitude [km]
    velocity [m/s] (relative to atmosphere)
    ram_area [m^2]
    COP      [m] (center of pressure vector, spacecraft frame)
    COM      [m] (center of mass vector, spacecraft frame) [m]
    cd       []  (drag coefficient, set=2.2 as default)
    lat, lon, time, f107, f107a, ap - NRLMSISE inputs (see defaults above)

    Returns
    drag_force  [N]   (forces vector, spacecraft frame)
    drag_torque [N*m] (torques vector about the COM, spacecraft frame)
    """

    NRLMSISE = pymsis.calculate(time, lon, lat, altitude, f107, f107a, [ap])
    # set version=0 for NRLMSISE-00 (standard in STK and GMAT)
    # NRLMSISE-2.1 is default version

    velocity = np.asarray(velocity, dtype=float)  # [m/s]

    density = NRLMSISE[0, 0]  # mass density [kg/m^3]

    speed = np.linalg.norm(velocity)

    if speed == 0:
        return np.zeros(3), np.zeros(3)  # no force, no torque

    v_hat = velocity / speed  # velocity unit vector

    pressure = 0.5 * density * speed**2  # [Pa]

    force_mag = pressure * cd * ram_area  # [N]

    drag_force = -force_mag * v_hat  # drag vector (opposite velocity) [N]

    moment_arm = np.asarray(COP) - np.asarray(COM)  # [m]

    drag_torque = np.cross(moment_arm, drag_force)  # torque vector [N*m]

    return drag_force, drag_torque
