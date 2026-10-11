# Acceleration-aware Kinematic Orienteering

Staged implementation: MOVNS for single-agent KOP, multi-agent KOP, then intermittent communication. Flight-time budgets are seconds; pre-arrival waits count, terminal presence is free. Collisions are ignored. Objectives are reward maximization and mean completion-time minimization.

See [implementation status](docs/implementation.md) and [specification](spec/README.md).

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[test]'
.venv/bin/python -m pytest -q
.venv/bin/topcc
```

The current stage runs single-agent and multi-agent MOVNS-KOP. Use `--mode team_kop` for the two-agent smoke instance. A matched LNS baseline is available for single-agent instances. Use `--max-seconds`, `--max-evaluations`, `--disable`, and `--output` to control and record runs. Input JSON requires `schema_version: 1`, `budget_unit: "seconds"`, task IDs/positions/rewards, explicit start/end, and per-agent budget and axis motion limits.
