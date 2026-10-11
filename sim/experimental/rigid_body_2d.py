"""
Two-dimensional rigid-body simulator with a PID controller.

uv run python sim/experimental/rigid_body_2d.py
"""

import numpy as np

# Physical constants
PI = np.pi

# Parameters
INERTIA = 1.0

# Control configs
KP, KI, KD = 10.0, 0.1, 1.0
MAX_CONTROL_TORQUE_NM = 5.0
DESIRED_THETA_RAD = 1.0

# Simulation configs
TIMESTEP_SEC = 0.01
TOTAL_TIME_SEC = 60
EXTERNAL_TORQUE_NM = 1.0


def state_derivative(state, torque_nm):
    # [w   tau/I]
    _, omega_rad_per_sec = state[0], state[1]
    return [omega_rad_per_sec, torque_nm / INERTIA]


def torque_pid_controller(
    state,
    desired_theta_rad,
    integrated_theta_error_rad_sec,
    dt,
):
    theta_rad, omega_rad_per_sec = state

    # error = theta_d - theta
    theta_error_rad = desired_theta_rad - theta_rad
    theta_error_rad = (theta_error_rad + PI) % (2 * PI) - PI
    error_rate_rad_per_sec = -omega_rad_per_sec

    # tau = kp * error + ki int_0^t(error) + kd de/dt
    torque_raw_nm = (
        KP * theta_error_rad
        + KI * integrated_theta_error_rad_sec
        + KD * error_rate_rad_per_sec
    )

    # Prevent integral windup
    pushing_into_saturation = (
        torque_raw_nm > MAX_CONTROL_TORQUE_NM and theta_error_rad > 0
    ) or (torque_raw_nm < -MAX_CONTROL_TORQUE_NM and theta_error_rad < 0)
    if not pushing_into_saturation:
        integrated_theta_error_rad_sec += theta_error_rad * dt

    # Clamp torque to allowed torque bounds
    torque_nm = np.clip(
        KP * theta_error_rad
        + KI * integrated_theta_error_rad_sec
        + KD * error_rate_rad_per_sec,
        -MAX_CONTROL_TORQUE_NM,
        MAX_CONTROL_TORQUE_NM,
    )

    return torque_nm, integrated_theta_error_rad_sec


def euler_step(state, torque_nm, dt):
    # x_new = x + dx/dt * dt
    theta_dot, omega_dot = state_derivative(state, torque_nm)
    theta_new = state[0] + theta_dot * dt
    theta_new = (theta_new + PI) % (2 * PI) - PI
    return [
        theta_new,
        state[1] + omega_dot * dt,
    ]


def visualize(state_history, timestep_sec):
    import plotly.graph_objects as go

    times_sec = [i * timestep_sec for i in range(len(state_history))]
    theta_rad = [state[0] for state in state_history]
    omega_rad_per_sec = [state[1] for state in state_history]
    slider_stride = max(1, (len(state_history) + 199) // 200)
    slider_indices = list(range(0, len(state_history), slider_stride))
    if slider_indices[-1] != len(state_history) - 1:
        slider_indices.append(len(state_history) - 1)

    figure = go.Figure(
        data=[
            go.Scatter(x=times_sec, y=theta_rad, name="theta (rad)"),
            go.Scatter(x=times_sec, y=omega_rad_per_sec, name="omega (rad/s)"),
        ],
        frames=[
            go.Frame(
                name=str(i),
                data=[
                    go.Scatter(x=times_sec[: i + 1], y=theta_rad[: i + 1]),
                    go.Scatter(x=times_sec[: i + 1], y=omega_rad_per_sec[: i + 1]),
                ],
            )
            for i in slider_indices
        ],
    )
    figure.update_layout(
        xaxis_title="Time (s)",
        yaxis_title="State",
        sliders=[
            {
                "steps": [
                    {
                        "method": "animate",
                        "label": f"{times_sec[i]:.1f}",
                        "args": [
                            [str(i)],
                            {
                                "mode": "immediate",
                                "frame": {"duration": 0, "redraw": True},
                            },
                        ],
                    }
                    for i in slider_indices
                ]
            }
        ],
    )
    figure.show()


def main():
    state = [0.0, 0.0]
    state_history = [state]

    for i in range(int(TOTAL_TIME_SEC // TIMESTEP_SEC)):
        if i == 0:
            integrated_theta_error_rad_sec = 0.0
        control_torque_nm, integrated_theta_error_rad_sec = torque_pid_controller(
            state,
            DESIRED_THETA_RAD,
            integrated_theta_error_rad_sec,
            TIMESTEP_SEC,
        )
        net_torque_nm = control_torque_nm + EXTERNAL_TORQUE_NM
        state = euler_step(state, net_torque_nm, TIMESTEP_SEC)
        state_history.append(state)

    # Plot the state vs. time
    visualize(state_history, TIMESTEP_SEC)


if __name__ == "__main__":
    main()
