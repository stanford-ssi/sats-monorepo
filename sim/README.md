# Arda satellite simulator

Run every registered scenario, save its telemetry under `sim/data/`, and open
the latest result in SSIFT:

```bash
uv run python sim/main.py
```

Run the repository tests:

```bash
uv run pytest
```

## Publishing telemetry

At every saved time, Arda re-evaluates the dynamics inside a scoped return
collector. Every numeric return value from functions under `arda.physics` is
captured under its module and function path, except functions whose names begin
with `_`. Nested dataclasses and mappings are expanded automatically, and field
names provide unit and frame metadata.

Model authors write ordinary functions: no telemetry calls, wrappers,
decorators, or central channel list. Any value that should appear in SSIFT must
be returned by a physics function; private local scratch values are not visible
outside that function.
