# Acceleration-aware Kinematic Orienteering

Staged implementation: MOVNS for single-agent KOP, multi-agent KOP, then intermittent communication. Flight-time budgets are seconds; pre-arrival waits count, terminal presence is free. Collisions are ignored. Objectives are reward maximization and mean completion-time minimization.

See [implementation status](docs/implementation.md) and [specification](spec/README.md).

The current `topcc` entry point runs only `team_kop_icc` through the
[TOP-CC-shaped rebuild](docs/topcc-rebuild.md). Its evaluation core is checked
against frozen trajectory, contact, staleness, bottleneck, and objective
fixtures. Historical single-agent, team-only, and LNS runs remain at the
`pre-topcc-rebuild-20261012` tag.

To find the saved results for stages 2–4, use the [results index](results/README.md). To run the eight synthetic scenario maps and interpret saved fronts, paths, and communication timelines, follow the [scenario tutorial](maps/scenarios/README.md).

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[test]'
.venv/bin/python -m pytest -q
.venv/bin/topcc
```

The current solver runs team KOP with intermittent communication. Use
`--max-seconds`, `--max-evaluations`, `--disable`, and `--output` to control and
record runs. Input JSON requires `schema_version: 1`, `budget_unit: "seconds"`,
task IDs/positions/rewards, explicit start/end, and per-agent budget and axis
motion limits. Historical commands below describe saved experiments from the
frozen tag.

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
.venv/bin/python scripts/plot_results.py results/step3/full.json /tmp/kop-team-plots
```

Communication and free waypoints are now available on `implementation/step4-intermittent-communication` via `--mode team_kop_icc`. Collisions remain ignored.

## Stage 4 results and data

[Communication report and plots](docs/experiments-icc.md) · [Tc frontier plot](results/step4/tc-independent-fronts.png) · [JSON summary](results/step4/summary.json) · [CSV summary](results/step4/summary.csv) · [fixed-bank sweep](results/step4/tc-common-bank.json).

The separate [eight-map scenario campaign](results/step4/scenarios/README.md) stores one bounded ICC search and plots for each synthetic map under `results/step4/scenarios/`.

For a detached one-hour-per-map campaign with per-iteration objective plots, run `sh scripts/start_long_scenario_campaign.sh`. The [scenario tutorial](maps/scenarios/README.md) explains the saved output and progress ledger.

The latest 120-second reruns for the first three maps, using interleaved per-agent candidate generation, are saved under [results/step4/scenarios_refactor_balanced_20261012_3maps](results/step4/scenarios_refactor_balanced_20261012_3maps/README.md), with validated fronts, paths, and objective-evolution plots. These runs reached only one or two outer iterations; see their operator counts in the saved JSON before attributing performance changes to every family.

The current ICC search uses a three-objective epsilon archive over negative reward, mean completion time, and communication violation $\max(0,\Delta-T_c)$. The reported reward–time front is the zero-violation slice. A separate dominated-solution archive uses crowding distance for search diversity. The eight enabled ICC families are `remove`, `replace`, `assignment`, `reorder`, `insert`, `excursion`, `meeting`, and `unlink`. Reward is collected only by explicit TASK visits; new result files declare `reward_policy: explicit_task_visits`, while older files retain their historical passage-based interpretation. Every ICC candidate receives deterministic route velocity DP refinement before scoring. Each neighborhood starts from an independent noisy ruin-and-recreate perturbation of the same selected archive member. The only destroy moves are route removal, contiguous sequence removal, and spatially related removal; repair discounts tasks already explicitly visited by another agent. Capped routing neighborhoods interleave proposals by agent in a fresh seeded order; communication neighborhoods interleave shuffled agent pairs, placing the bottleneck pair first. To compare different `Tc` bounds, run the optimizer independently for each bound. To launch scenarios 1–3 as independent background searches, pass an output directory and their map stems to `scripts/start_long_scenario_campaign.sh`; each map folder receives machine-readable results, accepted-front history, and plots. See the [scenario tutorial](maps/scenarios/README.md) and [neighborhood design](docs/neighborhood_structures.md).

The CLI permits an optional search allowance of up to 3,600 seconds. `--max-evaluations 1000000` and a raised `--max-iterations` can be used with it; see the [map tutorial](maps/scenarios/README.md). The saved campaign retains its original limits and results.

All ten stage-4 searches reached 2,000 evaluations in under 28 seconds. Independent-search best reward rose from 125 to 150 to 190 at Tc=2,5,10 seconds. These short runs do not establish a benefit from free waypoints; the report distinguishes operator activity, task-only controls, and a controlled geometric fixture.

Current ICC per-run JSON uses result schema version 4 and stores routes, meetings, trajectories, contact intervals, staleness, three-objective violation archive members, dominated search seeds, accepted-front history, and feasible-front indices at the run's `Tc`. Historical stage-4 campaign files remain schema versions 2 or 3. Instance schema remains version 1. Communication history rows are `[time, left_limit_peak, post_exchange_peak]`; final-clock rows are receivers and columns are sources. `feasible` means valid motion and individual flight budgets; zero violation determines recurrence feasibility.

Regenerate analysis without new searches:

```sh
.venv/bin/python scripts/save_icc_fixture.py
.venv/bin/python scripts/summarize_icc.py
```
