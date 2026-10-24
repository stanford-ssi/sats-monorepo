"""Passive rotations."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class Quaternion:
    """Normalized scalar-last quaternion mapping frame 1 coordinates to frame 2."""

    xyzw: FloatArray

    def __post_init__(self) -> None:
        xyzw = np.array(self.xyzw, dtype=np.float64, copy=True)
        if xyzw.shape != (4,) or np.linalg.norm(xyzw) == 0.0:
            raise ValueError("quaternion must be a nonzero shape-(4,) array")
        xyzw /= np.linalg.norm(xyzw)
        xyzw.setflags(write=False)
        object.__setattr__(self, "xyzw", xyzw)

    @classmethod
    def identity(cls) -> "Quaternion":
        return cls(np.array([0.0, 0.0, 0.0, 1.0]))

    @classmethod
    def from_axis_angle(cls, axis: FloatArray, angle_rad: float) -> "Quaternion":
        """Rotate about a vector in Frame 1 into Frame 2."""
        axis = np.asarray(axis, dtype=np.float64)
        axis_norm = np.linalg.norm(axis)
        if axis.shape != (3,) or axis_norm == 0.0:
            raise ValueError("axis must be a nonzero shape-(3,) array")
        half_angle_rad = -angle_rad / 2.0
        return cls(
            np.append(axis / axis_norm * np.sin(half_angle_rad), np.cos(half_angle_rad))
        )

    def as_dcm(self) -> FloatArray:
        """Return the passive DCM mapping Frame 1 to Frame 2."""
        x, y, z, w = self.xyzw
        return np.array(
            [
                [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
            ]
        )

    def derivative(
        self, angular_velocity_frame2_wrt_frame1_frame1_rad_per_s: FloatArray
    ) -> FloatArray:
        """Differentiate using angular velocity resolved in Frame 1."""
        vector = self.xyzw[:3]
        scalar = self.xyzw[3]
        angular_velocity = angular_velocity_frame2_wrt_frame1_frame1_rad_per_s
        return np.concatenate(
            (
                -0.5 * (scalar * angular_velocity - np.cross(angular_velocity, vector)),
                [0.5 * np.dot(angular_velocity, vector)],
            )
        )


def test_axis_angle_rotation_is_passive() -> None:
    frame1_to_frame2 = Quaternion.from_axis_angle(
        np.array([0.0, 0.0, 1.0]), np.pi / 2.0
    )

    np.testing.assert_allclose(
        frame1_to_frame2.as_dcm() @ np.array([1.0, 0.0, 0.0]),
        [0.0, -1.0, 0.0],
        atol=1e-12,
    )
