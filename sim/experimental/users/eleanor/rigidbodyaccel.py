
#Acceleration and angular acceleration of rigid body
import numpy as np

def compute_linear_acceleration(force, mass):
    return force / mass

def compute_gyroscopic_torque(omega, J):
    # w x (Jw) (aka w x H)
    return np.cross(omega, np.dot(J, omega))

def compute_angular_acceleration(tau, omega, J):
    #Euler eq: dw/dt = J^-1 * (tau - w x (Jw))
    J_inv = np.linalg.inv(J)
    torque = compute_gyroscopic_torque(omega, J)
    return np.dot(J_inv, tau - torque)

def compute_rigid_body_dynamics(mass, J, force, tau, omega):
    linear_accel = compute_linear_acceleration(force, mass)
    angular_accel = compute_angular_acceleration(tau, omega, J)
    return linear_accel, angular_accel
