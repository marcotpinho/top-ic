# Acceleration-aware Kinematic Orienteering

Staged implementation: MOVNS for single-agent KOP, multi-agent KOP, then intermittent communication. Flight-time budgets are seconds; pre-arrival waits count, terminal presence is free. Collisions are ignored. Objectives are reward maximization and mean completion-time minimization.

See [implementation status](docs/implementation.md) and [specification](spec/README.md).

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[test]'
.venv/bin/python -m pytest -q
.venv/bin/topcc
```

The current stage constructs and validates trajectories; search arrives in step 2. Input JSON requires `schema_version: 1`, `budget_unit: "seconds"`, task IDs/positions/rewards, explicit start/end, and per-agent budget and axis motion limits.
