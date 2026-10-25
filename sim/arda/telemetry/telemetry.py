"""Automatic telemetry capture from simulation result objects."""

import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, fields, is_dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]

_UNIT_SUFFIXES = (
    ("_rad_per_s2", "rad_per_s2"),
    ("_m_per_s2", "m_per_s2"),
    ("_rad_per_s", "rad_per_s"),
    ("_m_per_s", "m_per_s"),
    ("_kgm2", "kg_m2"),
    ("_per_s", "per_s"),
    ("_nm", "N_m"),
    ("_n", "N"),
    ("_m", "m"),
)


@dataclass(frozen=True)
class TelemetryMetadata:
    unit: str | None = None
    frame: str | None = None
    components: tuple[str, ...] | None = None


@contextmanager
def capture_returns(package: str = "arda.physics") -> Iterator[dict[str, object]]:
    """Capture function return values beneath a package while the context is active."""
    captured: dict[str, object] = {}
    previous_profile = sys.getprofile()
    root_package = package.partition(".")[0]

    def profile(frame, event: str, value: object) -> None:
        function_name = frame.f_code.co_name
        if event != "return" or value is None or function_name.startswith("_"):
            return
        module = frame.f_globals.get("__name__", "")
        if module != package and not module.startswith(f"{package}."):
            return
        node = captured
        for segment in module.removeprefix(f"{root_package}.").split("."):
            child = node.setdefault(segment, {})
            if not isinstance(child, dict):
                raise ValueError(f"telemetry path collision at {segment}")
            node = child
        name = function_name
        suffix = 2
        unique_name = name
        while unique_name in node:
            unique_name = f"{name}_{suffix}"
            suffix += 1
        node[unique_name] = value

    sys.setprofile(profile)
    try:
        yield captured
    finally:
        sys.setprofile(previous_profile)


def _numeric_value(value: object, path: str) -> FloatArray:
    try:
        result = np.array(value, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as error:
        raise TypeError(f"telemetry value is not numeric: {path}") from error
    if result.ndim > 1 or not np.all(np.isfinite(result)):
        raise ValueError(f"telemetry value must be a finite scalar or vector: {path}")
    result.setflags(write=False)
    return result


def _flatten(value: object, prefix: tuple[str, ...] = ()) -> dict[str, FloatArray]:
    """Flatten nested dataclasses and mappings into slash-separated numeric paths."""
    if isinstance(value, Mapping):
        flattened = {}
        for name, child in value.items():
            if not isinstance(name, str) or not name or "/" in name:
                raise ValueError(
                    "telemetry mapping keys must be nonempty path segments"
                )
            flattened.update(_flatten(child, (*prefix, name)))
        return flattened

    if is_dataclass(value) and not isinstance(value, type):
        data_fields = fields(value)
        # Quaternion is a transparent numeric wrapper; keep its owning field's path.
        if len(data_fields) == 1 and data_fields[0].name == "xyzw":
            return _flatten(value.xyzw, prefix)
        flattened = {}
        for data_field in data_fields:
            flattened.update(
                _flatten(getattr(value, data_field.name), (*prefix, data_field.name))
            )
        return flattened

    if not prefix:
        raise ValueError("telemetry samples must have named fields")
    path = "/".join(prefix)
    return {path: _numeric_value(value, path)}


def _metadata(path: str, value: FloatArray) -> TelemetryMetadata:
    name = path.rsplit("/", 1)[-1]
    stem = name
    unit = None
    for suffix, candidate in _UNIT_SUFFIXES:
        if name.endswith(suffix):
            stem = name.removesuffix(suffix)
            unit = candidate
            break

    frame = None
    if "_to_" in stem and "quat" in stem:
        source, target = stem.rsplit("_to_", 1)
        frame = f"{source.rsplit('_', 1)[-1].upper()} to {target}"
    else:
        for token in reversed(stem.split("_")):
            if token == "eci":
                frame = "ECI"
                break
            if token == "body":
                frame = "body"
                break

    components = None
    if value.ndim == 1:
        if value.size == 3:
            components = ("x", "y", "z")
        elif value.size == 4 and "quat" in name:
            components = ("x", "y", "z", "w")
        else:
            components = tuple(map(str, range(value.size)))
    return TelemetryMetadata(unit, frame, components)


@dataclass(frozen=True)
class Telemetry:
    time_s: FloatArray
    channels: Mapping[str, FloatArray]
    metadata: Mapping[str, TelemetryMetadata]

    def __post_init__(self) -> None:
        time_s = np.array(self.time_s, dtype=np.float64, copy=True)
        if time_s.ndim != 1 or not np.all(np.isfinite(time_s)):
            raise ValueError("telemetry time must be a finite one-dimensional array")
        channels = {
            path: np.array(values, dtype=np.float64, copy=True)
            for path, values in self.channels.items()
        }
        if any(not path for path in channels):
            raise ValueError("telemetry channel paths cannot be empty")
        if any(values.shape[:1] != time_s.shape for values in channels.values()):
            raise ValueError("telemetry channels must match the time axis")
        metadata = dict(self.metadata)
        if set(metadata) != set(channels):
            raise ValueError("telemetry metadata must match the channels")
        time_s.setflags(write=False)
        for values in channels.values():
            values.setflags(write=False)
        object.__setattr__(self, "time_s", time_s)
        object.__setattr__(self, "channels", channels)
        object.__setattr__(self, "metadata", metadata)

    @classmethod
    def from_samples(cls, time_s: ArrayLike, samples: Sequence[object]) -> "Telemetry":
        """Recursively capture every numeric field published in each sample."""
        time_s = np.asarray(time_s, dtype=np.float64)
        if time_s.ndim != 1 or len(samples) != time_s.size:
            raise ValueError("telemetry needs one sample per time value")
        if not samples:
            return cls(time_s, {}, {})

        flattened = [_flatten(sample) for sample in samples]
        paths = tuple(flattened[0])
        expected_paths = set(paths)
        shapes = {path: flattened[0][path].shape for path in paths}
        for sample in flattened:
            if set(sample) != expected_paths:
                raise ValueError("telemetry channels changed between samples")
            for path in paths:
                if sample[path].shape != shapes[path]:
                    raise ValueError(f"telemetry shape changed for {path}")

        channels = {
            path: np.stack([sample[path] for sample in flattened]) for path in paths
        }
        metadata = {path: _metadata(path, flattened[0][path]) for path in paths}
        return cls(time_s, channels, metadata)

    def __getitem__(self, channel: str) -> FloatArray:
        return self.channels[channel]


def test_telemetry_discovers_nested_model_outputs() -> None:
    @dataclass(frozen=True)
    class ModelOutput:
        force_eci_n: FloatArray
        active: float

    telemetry = Telemetry.from_samples(
        [0.0, 1.0],
        [
            {"physics": {"model": ModelOutput(np.array([1.0, 2.0, 3.0]), 1.0)}},
            {"physics": {"model": ModelOutput(np.array([4.0, 5.0, 6.0]), 0.0)}},
        ],
    )

    np.testing.assert_array_equal(
        telemetry["physics/model/force_eci_n"],
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
    )
    assert telemetry.metadata["physics/model/force_eci_n"] == TelemetryMetadata(
        unit="N", frame="ECI", components=("x", "y", "z")
    )
    np.testing.assert_array_equal(telemetry["physics/model/active"], [1.0, 0.0])
