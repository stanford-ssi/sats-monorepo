"""Simulator-independent numeric telemetry for SSIFT."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _vector(values: ArrayLike, name: str) -> FloatArray:
    vector = np.array(values, dtype=np.float64, copy=True)
    if vector.ndim != 1 or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a finite one-dimensional array")
    vector.setflags(write=False)
    return vector


@dataclass(frozen=True)
class Axis:
    name: str
    values: FloatArray
    label: str
    unit: str | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.label:
            raise ValueError("axis needs a name and label")
        object.__setattr__(self, "values", _vector(self.values, "axis values"))


@dataclass(frozen=True)
class Channel:
    path: str
    values: FloatArray
    axis: str = "time"
    unit: str | None = None
    frame: str | None = None
    group: str | None = None
    series: str | None = None

    def __post_init__(self) -> None:
        if not self.path or any(not part for part in self.path.split("/")):
            raise ValueError("channel path needs nonempty slash-separated parts")
        if not self.axis:
            raise ValueError("channel axis cannot be empty")
        if self.group is not None and (
            not self.group or any(not part for part in self.group.split("/"))
        ):
            raise ValueError("channel group needs nonempty slash-separated parts")
        if self.series is not None and not self.series:
            raise ValueError("channel series cannot be empty")
        object.__setattr__(self, "values", _vector(self.values, "channel values"))


@dataclass(frozen=True)
class Signal:
    """One scalar or component-labeled vector time series."""

    values: ArrayLike
    unit: str | None = None
    frame: str | None = None
    components: str | tuple[str, ...] | None = None


@dataclass(frozen=True)
class Dataset:
    name: str
    axes: tuple[Axis, ...]
    channels: tuple[Channel, ...]
    metadata: Mapping[str, str] = field(default_factory=dict)
    schema_version: int = field(default=2, init=False)

    def __post_init__(self) -> None:
        axes = tuple(self.axes)
        channels = tuple(self.channels)
        axis_sizes = {axis.name: axis.values.size for axis in axes}
        paths = [channel.path for channel in channels]
        selection_paths = {channel.group or channel.path for channel in channels}
        if not self.name or not axes:
            raise ValueError("dataset needs a name and at least one axis")
        if len(axis_sizes) != len(axes) or len(set(paths)) != len(paths):
            raise ValueError("axis names and channel paths must be unique")
        if any(
            right.startswith(f"{left}/")
            for left in paths
            for right in paths
            if left != right
        ):
            raise ValueError("channel paths cannot prefix other channel paths")
        if any(
            right.startswith(f"{left}/")
            for left in selection_paths
            for right in selection_paths
            if left != right
        ):
            raise ValueError("channel groups cannot prefix other channel groups")

        groups: dict[str, dict[str, Channel]] = {}
        for channel in channels:
            if channel.axis not in axis_sizes:
                raise ValueError(f"unknown channel axis: {channel.axis}")
            if channel.values.size != axis_sizes[channel.axis]:
                raise ValueError(f"channel length does not match axis: {channel.path}")
            if channel.group is None:
                continue
            if channel.series is None:
                raise ValueError(f"grouped channel needs a series: {channel.path}")
            members = groups.setdefault(channel.group, {})
            if channel.series in members:
                raise ValueError(f"duplicate series in group: {channel.group}")
            if members:
                reference = next(iter(members.values()))
                if (channel.unit, channel.frame) != (reference.unit, reference.frame):
                    raise ValueError(f"inconsistent group metadata: {channel.group}")
            members[channel.series] = channel

        object.__setattr__(self, "axes", axes)
        object.__setattr__(self, "channels", channels)
        object.__setattr__(self, "metadata", dict(self.metadata))

    @classmethod
    def from_timeseries(
        cls,
        name: str,
        time_s: ArrayLike,
        signals: Mapping[str, Signal],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> "Dataset":
        """Build a dataset from scalar and component-labeled signals."""
        channels = []
        for path, signal in signals.items():
            values = np.asarray(signal.values, dtype=np.float64)
            if values.ndim == 1:
                if signal.components is not None:
                    raise ValueError(f"scalar signal cannot have components: {path}")
                channels.append(
                    Channel(path, values, unit=signal.unit, frame=signal.frame)
                )
                continue
            if values.ndim != 2:
                raise ValueError(f"signal must be one- or two-dimensional: {path}")
            components = signal.components or tuple(map(str, range(values.shape[1])))
            if len(components) != values.shape[1] or len(set(components)) != len(
                components
            ):
                raise ValueError(f"signal components do not match its width: {path}")
            channels.extend(
                Channel(
                    f"{path}/{component}",
                    values[:, index],
                    unit=signal.unit,
                    frame=signal.frame,
                )
                for index, component in enumerate(components)
            )
        return cls(
            name=name,
            axes=(Axis("time", time_s, "Time", "s"),),
            channels=tuple(channels),
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "metadata": dict(self.metadata),
            "axes": {
                axis.name: {
                    "values": axis.values.tolist(),
                    "label": axis.label,
                    "unit": axis.unit,
                }
                for axis in self.axes
            },
            "channels": [
                {
                    "path": channel.path,
                    "axis": channel.axis,
                    "unit": channel.unit,
                    "frame": channel.frame,
                    "group": channel.group,
                    "series": channel.series,
                    "values": channel.values.tolist(),
                }
                for channel in self.channels
            ],
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), separators=(",", ":")), encoding="utf-8"
        )
        return path


def test_vector_signals_become_component_channels() -> None:
    dataset = Dataset.from_timeseries(
        "test",
        [0.0, 1.0],
        {"state/vector": Signal([[1.0, 2.0], [3.0, 4.0]], components=("x", "y"))},
    )
    assert [channel.path for channel in dataset.channels] == [
        "state/vector/x",
        "state/vector/y",
    ]


def test_dataset_rejects_mismatched_channel_length() -> None:
    try:
        Dataset(
            "bad",
            (Axis("time", [0.0, 1.0], "Time", "s"),),
            (Channel("value", [1.0]),),
        )
    except ValueError as error:
        assert "length" in str(error)
    else:
        raise AssertionError("mismatched channel was accepted")
