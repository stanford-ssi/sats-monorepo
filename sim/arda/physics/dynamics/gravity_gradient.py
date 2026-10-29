import numpy as np

"""
This code implements the gravitational gradient torque function, when given the vectors for the inertia of the satellite and radius of the body
we can calculate the gravitational gradient code using this function
"""

mu=3.986004418e14
def gravity_gradient_torque(r_body, inertia ):
    """
    r_body: Earth-center-to-satellite vector in body axes [m], shape (3,)
    inertia: satellite inertia matrix in body axes [kg m^2], shape (3, 3)
    mu: central body's gravitational parameter [m^3/s^2]; default Earth

    Returns torque in body axes [N m], shape (3,).
    """
    r_body = np.asarray(r_body, dtype=float)
    inertia = np.asarray(inertia, dtype=float)

    if r_body.shape != (3,) or inertia.shape != (3, 3):
        raise ValueError("Expected position shape (3,) and inertia shape (3, 3).")

    r = np.linalg.norm(r_body)
    if r == 0:
        raise ValueError("Orbital radius must be nonzero.")

    r_hat = r_body / r
    return (3.0 * mu / r**3) * np.cross(r_hat, inertia @ r_hat)


# Example satellite
I_body = np.diag([120.0, 100.0, 80.0])  # kg m^2
r_body = np.array([7.0e6, 1.0e6, 0.0])  # m

torque = gravity_gradient_torque(r_body, I_body)
print("Gravity-gradient torque [N m]:", torque)


