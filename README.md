# Acceleration-aware Kinematic Orienteering

Staged implementation: MOVNS for single-agent KOP, multi-agent KOP, then intermittent communication. Flight-time budgets are seconds; travel has no pre-arrival pauses; terminal presence is free. Collisions are ignored. Objectives are reward maximization and mean completion-time minimization.

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

Communication and free waypoints are now available on `implementation/step4-intermittent-communication`. Collisions remain ignored.

## Stage 4 results and data

[Communication report and plots](docs/experiments-icc.md) · [Tc frontier plot](results/step4/tc-independent-fronts.png) · [JSON summary](results/step4/summary.json) · [CSV summary](results/step4/summary.csv) · [fixed-bank sweep](results/step4/tc-common-bank.json).

The separate [eight-map scenario campaign](results/step4/scenarios/README.md) stores one bounded ICC search and plots for each synthetic map under `results/step4/scenarios/`.

For a detached one-hour-per-map campaign with per-iteration objective plots, run `sh scripts/start_long_scenario_campaign.sh`. The [scenario tutorial](maps/scenarios/README.md) explains the saved output and progress ledger.

The latest 120-second reruns for the first three maps, using interleaved per-agent candidate generation, are saved under [results/step4/scenarios_refactor_balanced_20261012_3maps](results/step4/scenarios_refactor_balanced_20261012_3maps/README.md), with validated fronts, paths, and objective-evolution plots. These runs reached only one or two outer iterations; see their operator counts in the saved JSON before attributing performance changes to every family.

The current ICC search reports reward and mean completion time. Its feasible epsilon archive `F` contains only solutions with zero ordered-pair communication violation; its C-TAEA-inspired pool `P` covers valid candidates outside `F` across 21 fixed reward–time subregions. `CV`, pair peaks, and integrated excess are constraints or diagnostics. Each iteration selects a base from `F` or `P`, applies 10–40% ruin-and-recreate, bounded communication repair, and VND. The eleven enabled ICC families are `remove`, `replace`, `assignment`, `reorder`, `insert`, `relay`, `free_near_visit`, `free_segment`, `unlink`, `velocity_change`, and `velocity_segment`. Reward comes only from explicit TASK visits. To compare different `Tc` bounds, run the optimizer independently for each bound. See the [scenario tutorial](maps/scenarios/README.md) and [neighborhood design](docs/neighborhood_structures.md).

The CLI permits an optional search allowance of up to 3,600 seconds. `--max-evaluations 1000000` and a raised `--max-iterations` can be used with it; see the [map tutorial](maps/scenarios/README.md). The saved campaign retains its original limits and results.

## Saving a new experiment

Run new experiments through `scripts/run_experiment.py` so each result directory
contains the result JSON, neighborhood execution log, plots, agent-path animation, run information,
reproduction script, and a README generated from
[`docs/templates/README.md`](docs/templates/README.md):

```sh
.venv/bin/python scripts/run_experiment.py \
  --output-dir results/my-experiment \
  -- --instance maps/probes/ten_rewards_origin/instance.json \
     --seed 42 --recurrence-bound 4 --max-seconds 120
```

The generated `results/my-experiment/reproduce.sh` repeats the same command.

`paths-animation.gif` animates the same solution as `paths.png`, using a shared
mission clock, exact quadratic motion, and effective communication links. Agents
remain at their destinations after arrival. The GIF plays the full mission in
approximately 12 seconds at 15 frames per second and is generated after the search.

All ten stage-4 searches reached 2,000 evaluations in under 28 seconds. Independent-search best reward rose from 125 to 150 to 190 at Tc=2,5,10 seconds. These short runs do not establish a benefit from free waypoints; the report distinguishes operator activity, task-only controls, and a controlled geometric fixture.

Current ICC per-run JSON uses result schema version 7. It publishes only the feasible two-objective reward–time archive and stores routes, trajectories, contacts, staleness, archive history, pool coverage/age, repair outcomes, cache rates, operator counters, and convoy diagnostics. Communication violation is the sum of ordered-pair peak-age excesses over `Tc`; it is a constraint and pool diagnostic. Historical schemas retain their original meaning. Instance schema remains version 1.

Regenerate analysis without new searches:

```sh
.venv/bin/python scripts/save_icc_fixture.py
.venv/bin/python scripts/summarize_icc.py
```
