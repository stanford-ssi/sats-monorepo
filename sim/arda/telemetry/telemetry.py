"""Collected simulation time series."""

from dataclasses import dataclass

from arda.types import FloatArray


@dataclass(frozen=True)
class Telemetry:
    time_s: FloatArray
    channels: dict[str, FloatArray]

    @classmethod
    def from_state_history(
        cls, time_s: FloatArray, state_history: FloatArray
    ) -> "Telemetry":
        return cls(
            time_s,
            {
                "position_eci_m": state_history[:, :3],
                "velocity_eci_m_per_s": state_history[:, 3:6],
                "quat_eci_to_body": state_history[:, 6:10],
                "angular_velocity_body_wrt_eci_eci_rad_per_s": state_history[:, 10:13],
            },
        )

    def __getitem__(self, channel: str) -> FloatArray:
        return self.channels[channel]
