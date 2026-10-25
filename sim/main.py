"""Run all registered scenarios, save their data, and open SSIFT.

From the repository root:
    uv run python sim/main.py
"""

from pathlib import Path

from arda.simulator import run
from arda.telemetry import Telemetry
from scenarios import SCENARIOS
from ssift import Dataset, Signal, serve

_DATA_DIRECTORY = Path(__file__).with_name("data")


def _dataset(name: str, telemetry: Telemetry) -> Dataset:
    return Dataset.from_timeseries(
        name,
        telemetry.time_s,
        {
            path: Signal(
                values,
                unit=telemetry.metadata[path].unit,
                frame=telemetry.metadata[path].frame,
                components=telemetry.metadata[path].components,
            )
            for path, values in telemetry.channels.items()
        },
        metadata={"source": "arda"},
    )


def main() -> None:
    datasets = []
    for make_scenario in SCENARIOS:
        scenario = make_scenario()
        telemetry = run(scenario, progress=True)
        dataset = _dataset(scenario.name, telemetry)
        path = dataset.save(
            _DATA_DIRECTORY / f"{scenario.name.lower().replace(' ', '_')}.json"
        )
        datasets.append(dataset)
        print(f"Saved {telemetry.time_s.size} samples to {path}")

    serve(datasets[-1])


if __name__ == "__main__":
    main()
