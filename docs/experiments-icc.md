# Stage 4 — intermittent communication experiments

Ten optimizer starts on all 19 authentic Tsiligirides OP2 tasks, with two new 20-second agent budgets, range 2 m, handshake 0.5 s, and componentwise velocity/acceleration limits 3 m/s and 1.5 m/s². Collisions are ignored. The archive minimizes only negative reward and mean completion time with epsilon widths 1 and 0.1 s; delta is a constraint/guide.

| Run | Tc | Seed | Disabled | Free cap | Evaluations | Wall s | Reward | Front | Free-front points | HV |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| tc2-seed42 | 2 | 42 | — | 3 | 2000 | 21.532 | 125 | 15 | 0 | 1212.925 |
| tc5-seed42 | 5 | 42 | — | 3 | 2000 | 23.022 | 150 | 17 | 0 | 1314.041 |
| tc10-seed42 | 10 | 42 | — | 3 | 2000 | 27.193 | 190 | 21 | 0 | 1353.767 |
| tc5-seed7 | 5 | 7 | — | 3 | 2000 | 22.682 | 160 | 14 | 0 | 1388.861 |
| without-wait | 5 | 42 | wait | 3 | 2000 | 22.989 | 150 | 17 | 0 | 1314.041 |
| without-meeting | 5 | 42 | meeting | 3 | 2000 | 22.936 | 150 | 17 | 0 | 1314.041 |
| without-free_move | 5 | 42 | free_move | 3 | 2000 | 23.118 | 150 | 17 | 0 | 1314.041 |
| without-free_remove | 5 | 42 | free_remove | 3 | 2000 | 23.178 | 150 | 17 | 0 | 1314.041 |
| task-only-seed42 | 5 | 42 | — | 0 | 2000 | 22.745 | 150 | 17 | 0 | 1314.041 |
| task-only-seed7 | 5 | 7 | — | 0 | 2000 | 27.666 | 160 | 14 | 0 | 1457.439 |

## Protocol and interpretation

Each search has a 45-second soft runtime, 2,000-evaluation/80-iteration limits, and a 120-second hard subprocess timeout. All ten starts are recorded before execution; there are no retries. Four singleton ablations remove the new wait, meeting, free_move, and free_remove families. The six inherited task/assignment families were individually tested in stages 2/3 and are retained here. Task-only controls set the free-waypoint cap to zero while retaining task-location rendezvous. Matched full/task-only seeds 42 and 7 runs provide a small sensitivity comparison, not statistical significance.

The independent-search Tc plot mixes changed feasibility and changed search trajectories. It need not be monotone under a finite stochastic budget. The common-bank plot instead filters exactly the same stored physically valid trajectories by their Tc-independent Delta, then computes an exact nondominated front of that finite bank; its feasible counts, best reward and hypervolume are checked monotone. Neither plot establishes the unrestricted global Pareto front.

Operator activity matters: inspect each run’s `statistics.operators`. The seed 42 baseline can spend its fixed evaluation budget in inherited task neighborhoods before invoking communication families; an identical ablation outcome with no baseline activity is uninformative about that family. Seed 7 exercises communication operators and provides the paired task-only comparison. A controlled independent fixture additionally isolates the geometric advantage of a free rendezvous position.

All recorded searches reached the same 2,000-evaluation limit before the wall deadline. None of the independently optimized archive representatives contains FREE visits on this dense instance. At seed 7, allowing free positions produced the same best reward 160 but lower hypervolume than the task-only control; no benchmark advantage is established. The fixed-state geometric fixture below has a narrower claim.

## Controlled free-position fixture

[Fixture JSON](../results/step4/controlled-free-fixture.json) fixes each agent’s task assignment/order and zero visit velocities, and compares no meeting, meetings at either existing task, and an off-task meeting at (5,0). The free meeting has Delta 5.02223 s and satisfies Tc=5.05 s; the no-meeting and task-location alternatives have Delta 5.21540 s, 6.26520 s, and 5.09363 s and fail that bound. Every variant is independently validated. This isolates a spatial feasibility improvement for these fixed routes; it does not prove all task-only assignments or trajectories infeasible.

![Controlled free position](../results/step4/controlled-free-free-waypoints.png)

Hypervolume reference is (0,20) in minimization coordinates (-reward, mean time), shared across all comparisons. Practical wall stops can yield unequal evaluation counts. Prefix candidate limits, finite velocity menus and capped free positions are explicit algorithmic restrictions. A zero observed ablation effect does not prove a family useless.

Every exported front and candidate-bank solution is independently checked from saved data: motion/velocity continuity, axis bounds, budgets, declared visit states/waits, meeting overlap, incidental task union, raw/effective contacts using companion-matrix quartic roots, and Delta using reverse temporal reachability. The validator does not call production connectors, contact extraction, or propagation. Unresolved production contacts are counted/rejected, not treated as feasible. Ledger entries record checks and residuals. Independent polynomial solvers can disagree on first-visitor order for sub-tolerance simultaneous arrivals, so diagnostic attribution is checked against earliest arrival within 2e-6; union reward remains exact over the verified task set. The last saved bank was revalidated under that policy without another optimizer start, preserving its original validation error in the ledger.

## Parseable artifacts

[Run ledger](../results/step4/ledger.json), [independent validation summary](../results/step4/validation-summary.json), [summary JSON](../results/step4/summary.json), [summary CSV](../results/step4/summary.csv), [fixed-bank sweep JSON](../results/step4/tc-common-bank.json), and per-run schema-version 2 JSON contain full routes, meetings, actual visit times, accelerated trajectories, raw/effective contacts, clock history, bottleneck, Delta, violation, working pool and a bounded candidate bank. Source/instance hashes and software versions are recorded; the artifact manifest hashes the files.

Each saved search JSON also has a same-named folder under [results/step4](../results/step4/) with Pareto, path, velocity, contact/staleness, and free-waypoint figures. Regenerate these from saved data with `.venv/bin/python scripts/plot_saved_stage_results.py --stage 4`; this starts no searches.

Regenerate plots and summaries without additional optimizer runs:

```sh
.venv/bin/python scripts/save_icc_fixture.py
.venv/bin/python scripts/summarize_icc.py
```

For reproduction in a fresh output directory, `scripts/run_icc_campaign.py --output-dir NEW_DIRECTORY` refuses to overwrite an existing ledger. Existing recorded outputs should not be silently replaced.

![Independent searches](../results/step4/tc-independent-fronts.png)

![Fixed trajectory bank](../results/step4/tc-common-bank-fronts.png)

![Ablations](../results/step4/ablations.png)

![Contact and staleness timeline](../results/step4/tc5-communication.png)

![Paths and velocity](../results/step4/tc5-paths-speed.png)
