import numpy as np
import pymsis

# Default NRLMSISE-00 inputs (Dawn over Stanford on the equinox)
DEFAULT_LAT = 37.4275  # north positive (geodetic)
DEFAULT_LON = -122.1697  # east positive
DEFAULT_TIME = np.datetime64("2026-03-20T14:09")
# Moderate solar activity
DEFAULT_F107 = 150.0  # daily F10.7 solar flux (sfu)
DEFAULT_F107A = 150.0  # 81-day average F10.7 (sfu)
DEFAULT_AP = 4.0  # daily geomagnetic Ap index


def atm_density_drag_torque(
    altitude_km,
    velocity_m_per_s,
    ram_area_m2,
    center_of_pressure_m,
    center_of_mass_m,
    drag_coefficient=2.2,
    lat=DEFAULT_LAT,
    lon=DEFAULT_LON,
    time=DEFAULT_TIME,
    f107_sfu=DEFAULT_F107,
    f107a_sfu=DEFAULT_F107A,
    ap=DEFAULT_AP,
):
    """
    Compute the aerodynamic drag force and torque on a satellite.

    Inputs
    altitude_km          (geodetic)
    velocity_m_per_s     (relative to atmosphere)
    ram_area_m2
    center_of_pressure_m (3d vector, spacecraft frame)
    center_of_mass_m     (3d vector, spacecraft frame)
    drag_coefficient     (set=2.2 as default)
    lat, lon             (geodetic latitude and longitude)
    time                 ("YYYY-DD-HHTMM:SS")
    f107, f107a          (measures of daily and long-term solar flux)
    ap                   (geomagnetic ap index)

    Returns
    drag_force_N         (forces vector, spacecraft frame)
    drag_torque_Nm       (torques vector about the COM, spacecraft frame)
    """

    NRLMSISE = pymsis.calculate(time, lon, lat, altitude_km, f107_sfu, f107a_sfu, [ap])
    # set version=0 for NRLMSISE-00 (standard in STK and GMAT)
    # NRLMSISE-2.1 is default version

    velocity_m_per_s = np.asarray(velocity_m_per_s, dtype=float)  # [m/s]

    density_kg_per_m3 = NRLMSISE[0, 0]  # mass density [kg/m^3]

    speed = np.linalg.norm(velocity_m_per_s)

    if speed == 0:
        return np.zeros(3), np.zeros(3)  # no force, no torque

    v_hat = velocity_m_per_s / speed  # velocity unit vector

    pressure = 0.5 * density_kg_per_m3 * speed**2  # [Pa]

    force_mag = pressure * drag_coefficient * ram_area_m2  # [N]

    drag_force_N = -force_mag * v_hat  # drag vector (opposite velocity) [N]

    moment_arm_m = np.asarray(center_of_pressure_m) - np.asarray(
        center_of_mass_m
    )  # [m]

    drag_torque_Nm = np.cross(moment_arm_m, drag_force_N)  # torque vector [N*m]

    return density_kg_per_m3, drag_force_N, drag_torque_Nm
