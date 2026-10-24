"""Run all registered scenarios.

From the repository root:
    uv run python sim/main.py
"""

from arda.simulator import run
from scenarios import SCENARIOS


def main() -> None:
    for make_scenario in SCENARIOS:
        scenario = make_scenario()
        telemetry = run(scenario, progress=True)
        print(
            f"{scenario.name}: {telemetry.time_s[-1]:.0f} s, "
            f"{telemetry.time_s.size} samples"
        )


if __name__ == "__main__":
    main()
