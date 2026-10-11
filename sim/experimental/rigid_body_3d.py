"""
Intermediate-axis theorem with torque-free RK4 integration.

uv run python sim/experimental/rigid_body_3d.py
"""

import numpy as np
import plotly.graph_objects as go

HALF_SIZE = np.array([1.0, 0.6, 0.3])
INERTIA = np.diag((np.sum(HALF_SIZE**2) - HALF_SIZE**2) / 3)
DT = 0.01
DURATION = 12.0


def derivative(state):
    quaternion, omega = state[:4], state[4:]
    q_vector, q_scalar = quaternion[:3], quaternion[3]
    quaternion_dot = 0.5 * np.concatenate(
        (q_scalar * omega + np.cross(q_vector, omega), [-q_vector @ omega])
    )
    omega_dot = np.linalg.solve(INERTIA, -np.cross(omega, INERTIA @ omega))
    return np.concatenate((quaternion_dot, omega_dot))


def rk4_step(state, dt):
    k1 = derivative(state)
    k2 = derivative(state + dt * k1 / 2)
    k3 = derivative(state + dt * k2 / 2)
    k4 = derivative(state + dt * k3)
    state = state + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6
    state[:4] /= np.linalg.norm(state[:4])
    return state


def integrate(initial_state, duration=DURATION, dt=DT):
    times = np.arange(round(duration / dt) + 1) * dt
    state = np.array(initial_state, dtype=float)
    state[:4] /= np.linalg.norm(state[:4])
    states = [state]
    for _ in times[1:]:
        states.append(rk4_step(states[-1], dt))
    return times, np.array(states)


def rotate(quaternion, vectors):
    cross = np.cross(quaternion[:3], vectors)
    return vectors + 2 * quaternion[3] * cross + 2 * np.cross(quaternion[:3], cross)


def visualize(times, states):
    corners = np.array(
        [[x, y, z] for x in (-1, 1) for y in (-0.6, 0.6) for z in (-0.3, 0.3)]
    )
    frame_indices = np.linspace(0, len(times) - 1, min(200, len(times)), dtype=int)

    def pose(index):
        quaternion = states[index, :4]
        body = rotate(quaternion, corners)
        middle_axis = rotate(quaternion, np.array([0.0, 1.3, 0.0]))
        return [
            go.Mesh3d(
                x=body[:, 0],
                y=body[:, 1],
                z=body[:, 2],
                alphahull=0,
                color="royalblue",
                opacity=0.5,
                name="Body",
            ),
            go.Scatter3d(
                x=[-middle_axis[0], middle_axis[0]],
                y=[-middle_axis[1], middle_axis[1]],
                z=[-middle_axis[2], middle_axis[2]],
                mode="lines+markers",
                line={"color": "orange", "width": 8},
                name="Intermediate body axis",
            ),
        ]

    angular_momentum = rotate(states[0, :4], INERTIA @ states[0, 4:])
    angular_momentum = 1.4 * angular_momentum / np.linalg.norm(angular_momentum)
    figure = go.Figure(
        data=pose(0)
        + [
            go.Scatter3d(
                x=[0, angular_momentum[0]],
                y=[0, angular_momentum[1]],
                z=[0, angular_momentum[2]],
                mode="lines+markers",
                line={"color": "black", "width": 7},
                name="Fixed angular momentum",
            )
        ],
        frames=[
            go.Frame(name=str(i), data=pose(i), traces=[0, 1]) for i in frame_indices
        ],
    )
    figure.update_layout(
        title="Intermediate-axis instability",
        scene={
            "xaxis": {"range": [-1.5, 1.5]},
            "yaxis": {"range": [-1.5, 1.5]},
            "zaxis": {"range": [-1.5, 1.5]},
            "aspectmode": "cube",
        },
        sliders=[
            {
                "currentvalue": {"prefix": "Time: ", "suffix": " s"},
                "steps": [
                    {
                        "method": "animate",
                        "label": f"{times[i]:.2f}",
                        "args": [
                            [str(i)],
                            {
                                "mode": "immediate",
                                "frame": {"duration": 0, "redraw": True},
                            },
                        ],
                    }
                    for i in frame_indices
                ],
            }
        ],
        updatemenus=[
            {
                "type": "buttons",
                "showactive": False,
                "buttons": [
                    {
                        "label": "Play",
                        "method": "animate",
                        "args": [
                            None,
                            {
                                "fromcurrent": True,
                                "frame": {"duration": 45, "redraw": True},
                            },
                        ],
                    },
                    {
                        "label": "Pause",
                        "method": "animate",
                        "args": [[None], {"mode": "immediate"}],
                    },
                ],
            }
        ],
        margin={"l": 0, "r": 0, "t": 50, "b": 0},
    )
    return figure


def main():
    # Identity attitude; spin mostly about y with a tiny destabilizing perturbation.
    initial_state = [0, 0, 0, 1, 0.01, 2.0, 0.01]
    times, states = integrate(initial_state)
    visualize(times, states).show()


if __name__ == "__main__":
    main()
