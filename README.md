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

## Implementation branches and experimental results

- `implementation/step1-foundation`: motion, instance schema, continuous evaluator.
- `implementation/step2-single-kop`: single-agent MOVNS, epsilon archive, five neighborhood ablations, matched LNS, plots.
- `implementation/step3-team-kop`: inherits step 2, adds team evaluation and assignment moves, six neighborhood ablations and plots.

The final archive uses epsilon-box dominance (defaults reward width 1, time width 0.1 seconds), not crowding distance. Exactly ten optimizer starts per experimental stage are recorded, including superseded attempts. All completed runs lasted under 46 seconds; final integrated correctness suite passes 30 tests.

[Single-agent report and plots](docs/experiments-step2.md) · [Team report and plots](docs/experiments-team.md) · [Benchmark provenance](benchmarks/tsiligirides/README.md). Data retain all 19 tasks from the primary Tsiligirides OP2 source; the 30-second single-agent and 20-second per-agent team budgets are explicit new KOP budgets, not conversions of the original distance budget.

Regenerate plots without running optimization:

```sh
.venv/bin/python scripts/plot_results.py results/step2/epsilon-full.json /tmp/kop-single-plots
.venv/bin/python scripts/plot_results.py experiments/team/full.json /tmp/kop-team-plots
```

Communication and free waypoints are planned for the next stage and currently rejected.
