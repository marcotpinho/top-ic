# Acceleration-aware Kinematic Orienteering

Staged implementation: MOVNS for single-agent KOP, multi-agent KOP, then intermittent communication. Flight-time budgets are seconds; pre-arrival waits count, terminal presence is free. Collisions are ignored. Objectives are reward maximization and mean completion-time minimization.

See [implementation status](docs/implementation.md) and [specification](spec/README.md).

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[test]'
.venv/bin/python -m pytest -q
.venv/bin/topcc
```

The current stage runs single-agent, multi-agent, and intermittent-communication MOVNS-KOP. Use `--mode team_kop` for the two-agent smoke instance. A matched LNS baseline is available for single-agent instances. Use `--max-seconds`, `--max-evaluations`, `--disable`, and `--output` to control and record runs. Input JSON requires `schema_version: 1`, `budget_unit: "seconds"`, task IDs/positions/rewards, explicit start/end, and per-agent budget and axis motion limits.

## Implementation branches and experimental results

- `implementation/step1-foundation`: motion, instance schema, continuous evaluator.
- `implementation/step2-single-kop`: single-agent MOVNS, epsilon archive, five neighborhood ablations, matched LNS, plots.
- `implementation/step3-team-kop`: inherits step 2, adds team evaluation and assignment moves, six neighborhood ablations and plots.
- `implementation/step4-intermittent-communication`: inherits step 3, adds continuous contacts/propagation, stopped rendezvous, free positions, working-pool guidance, and Tc sweeps.

The final archive uses epsilon-box dominance (defaults reward width 1, time width 0.1 seconds), not crowding distance. Exactly ten optimizer starts per experimental stage are recorded, including superseded attempts. All completed runs lasted under 46 seconds; the final stage-4 correctness suite passes 70 tests.

[Single-agent report and plots](docs/experiments-step2.md) · [Team report and plots](docs/experiments-team.md) · [Benchmark provenance](benchmarks/tsiligirides/README.md). Data retain all 19 tasks from the primary Tsiligirides OP2 source; the 30-second single-agent and 20-second per-agent team budgets are explicit new KOP budgets, not conversions of the original distance budget.

Regenerate plots without running optimization:

```sh
.venv/bin/python scripts/plot_results.py results/step2/epsilon-full.json /tmp/kop-single-plots
.venv/bin/python scripts/plot_results.py experiments/team/full.json /tmp/kop-team-plots
```

Communication and free waypoints are now available on `implementation/step4-intermittent-communication` via `--mode team_kop_icc`. Collisions remain ignored.

## Stage 4 results and data

[Communication report and plots](docs/experiments-icc.md) · [Tc frontier plot](experiments/icc/tc-independent-fronts.png) · [JSON summary](experiments/icc/summary.json) · [CSV summary](experiments/icc/summary.csv) · [fixed-bank sweep](experiments/icc/tc-common-bank.json).

All ten stage-4 searches reached 2,000 evaluations in under 28 seconds. Independent-search best reward rose from 125 to 150 to 190 at Tc=2,5,10 seconds. These short runs do not establish a benefit from free waypoints; the report distinguishes operator activity, task-only controls, and a controlled geometric fixture.

Full per-run JSON stores routes, meetings, actual visit times, trajectories, raw/effective contact intervals, staleness history, Delta, constraint violation, and candidate/working pools. Instance schema remains version 1; result schema is version 2. History rows are `[time, left_limit_peak, post_exchange_peak]`; final-clock rows are receivers and columns are sources. Use `feasible` for overall feasibility and `motion_budget_valid` for eligibility before communication; numerical `validation_status` is distinct. Fixed-bank sweep points retain their source-run metadata and explicitly record `evaluated_Tc`.

Regenerate analysis without new searches:

```sh
.venv/bin/python scripts/save_icc_fixture.py
.venv/bin/python scripts/summarize_icc.py
```
