# Implementation milestones

## Step 1 — foundation

Branch: `implementation/step1-foundation`. Implemented versioned JSON instances with explicit seconds budgets, immutable visits and solution decisions, a cached deterministic box-bounded double-integrator connector, continuous task-passage evaluation, and source/installed CLI entry points. Collision constraints are deliberately absent. Team search, MOVNS, communication, and FREE visits are not enabled on this branch.

The connector uses integrated upper/lower Lipschitz velocity envelopes. Their piecewise-quadratic displacement bounds yield candidate common-duration boundaries; convex interpolation constructs a feasible profile on each axis. This differs from reproducing KOP's exact profile-enumeration code and is documented as an independently derived equivalent reachability method for axis-box bounds. Degenerate identical states support zero-duration connections.

Validation: `.venv/bin/python -m pytest -q` passed 8 tests, including 80 random connections, analytic rest-to-rest durations, a sampled-velocity linear-programming reference, wait/budget accounting, incidental reward passage, schema round-trip, and coincident depots. `python main.py` and installed `topcc` both construct the direct smoke trajectory.

Setup: `uv venv --python 3.12 .venv`, then `uv pip install --python .venv/bin/python -e '.[test]'`. Run `topcc --instance instance.json` for a direct-route foundation check. Legacy distance-map files are rejected until explicitly converted to a seconds-budget instance.

Known limits: componentwise bounds only; no magnitude/jerk/collision constraints; numerical residual tolerance is 2e-7; no search in this stage. Existing legacy search modules are replaced in step 2 and are not invoked by this entry point.

## Step 2 — single-agent MOVNS-KOP

Branch: `implementation/step2-single-kop`, copied from step 1. Implemented five independently disableable neighborhoods: insert, remove, replace, reorder (relocate/reversal), and visit velocity (including wait removal). The runner lazily evaluates candidates, uses safe time lower bounds, caches complete immutable evaluations, shakes/VND with a seeded RNG, and archives only the two-objective feasible front. Equal objectives do not mutually dominate; alternate physical solutions remain separate exploration seeds. Initialization is bounded to 20% of the evaluation budget so it cannot consume the whole experiment before VND.

A KOP-inspired destroy/greedy-rebuild LNS baseline uses the same connector, velocity menu, evaluator, and limits. It is an independently implemented adapted baseline, not the authors' software. No nonlinear optimization runs inside evaluation. Communication and free waypoints remain disabled.

Validation: 14 tests pass, including exact finite-menu front comparison on a two-task instance, archive equality, deterministic fixed-count runs, neighborhood guards, infeasible direct route handling, portable output, and a bounded LNS run. Source/installed CLI produces three nondominated points for the smoke instance at 200 evaluations. These fixture tests are correctness checks, distinct from the experimental run cap.

Example: `topcc --mode single_kop --max-seconds 60 --max-evaluations 4000 --output results/single.json`. Use `--disable insert` (or another family) for one-neighborhood ablation. Experiments and visualizations are added separately on this branch after this core milestone.

Limitations: visit velocity is discretized (default four headings, speed fractions 0/0.5/1); no global continuous-state optimality claim; neighborhood traversal can depend on enumeration and practical wall-time stopping. Unit tests use fixed evaluation budgets for repeatability.

## Step 3 — multi-agent KOP

Branch: `implementation/step3-team-kop`, copied from step 2. The evaluator and runner support multiple agents with individual seconds budgets, global reached-task union, deterministic first-visitor diagnostics, and mean final arrival as the expenditure objective. Identical agents may cross/co-locate; there are no collision checks. Early agents remain stationary through later query times without increasing expenditure.

The sixth neighborhood, `assignment`, enumerates cross-agent transfer, two-task exchange with destination velocity-state enumeration, and tail exchange with stopped-state reconstruction. Existing insert/remove/replace/reorder/velocity neighborhoods operate on all agents. Compound shaking can edit multiple routes. No identity symmetry canonicalization is used yet, so heterogeneous agents are never incorrectly exchanged.

Validation: 21 tests pass. New tests cover the M=1 reduction, shared reward, mean versus maximum completion, individual budget violation, empty agent expenditure, terminal presence, heterogeneous transfers, co-location, agent permutations, and a tiny exhaustive assignment/order front. All exported fixture-front trajectories pass independent integration/bound validation. Team LNS is not advertised; the KOP-inspired LNS comparison is single-agent only. Communication/FREE visits are explicitly rejected pending step 4.

Example: `topcc --mode team_kop --max-seconds 60 --max-evaluations 4000 --output results/team.json`; `--disable assignment` removes all cross-agent assignment moves, including shaking. Plot and benchmark results are recorded separately after the parallel experiments.
