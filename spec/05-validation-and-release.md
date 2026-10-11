# Step 5: experiments, performance, and integration

## 5.1 Validation layers

Maintain reference Python implementations before accelerating kernels. Add unit tests for model invariants/motion/contacts/propagation/archive, integration tests for all three modes, and independent tiny-instance oracles. Property tests should check continuity, budget units, permutation invariance for identical agents, strict dominance, monotonic feasibility in T_c for a fixed solution, and deterministic evaluation of serialized trajectories.

Cross-check numerical contact boundaries with independent high-accuracy calculations and sampled diagnostics. Sampling alone cannot prove no short gap exists. Construct difficult tangency and almost-handshake cases intentionally. Report uncertainty separately from proven violation.

Exhaustive tiny oracles prove optimality only over the finite visit-state/waypoint set enumerated. They do not certify globally optimal continuous free positions. A direct-path infeasibility check must use the validated connector/bounds and endpoint assumptions.

## 5.2 Experiment matrix

| Stage | Factors | Comparisons |
|---|---|---|
| Single KOP | Task count, time budget tightness, heading/speed menu size, acceleration limit | MOVNS versus KOP-inspired LNS with matched motion and scalar or two-objective protocol |
| Team KOP | Agent count, spatial distribution, time budget, assignment imbalance | Intra-route only versus transfer/exchange/group moves; M=1 reduction |
| ICC | R, δ, T_c, free-waypoint cap, movement step schedule | No communication baseline; task-only meetings; free meetings; waits/state moves on/off |
| Runtime | Trajectory piece count, pair count, root difficulty, archive size | Full evaluator versus checked caching/incremental implementations |

Use fixed instance IDs and predefined seeds, identical computation budgets across variants, and separate tuning/held-out cases. Start with at least ten seeds per exploratory condition; expand where variability warrants it. State this as an experimental default, not a statistical guarantee.

Report feasible-run rate, reward/time fronts, hypervolume with a fixed documented reference point, best reward at matched time thresholds, communication violation for unsuccessful runs, connector/evaluator cost, and distributions across seeds. Normalize only with common transformations, not separate per-algorithm scales. Include task/state/meeting neighborhood ablations and the effect of waypoint/menu discretization.

Do not infer that smaller observed Δ in a run increases Pareto quality; it is a guide/feasibility diagnostic. Do not compare the old RSSI objective front with the new one as if they solved the same problem.

## 5.3 Performance work after correctness

Profile construction, quartic interval extraction, propagation, neighborhood generation, and archive operations separately. Optimize the measured bottleneck:

1. Lazy candidates and safe cheap screening.
2. Exact connector caches and unchanged-agent trajectory reuse.
3. Changed-pair contacts and horizon-aware stationary extension updates.
4. Checkpointed propagation with full-reference parity tests.
5. Vectorized/Numba kernels for stable APIs, then deterministic parallel candidate evaluation if beneficial.

Avoid a Bloom filter as the sole visited-state test because false positives prune candidates. If used for speed, verify hits in an exact bounded store. Make cache size and eviction deterministic where reproducibility matters. Batch outcomes in generation order so parallel completion order does not change archive acceptance.

A long-runtime graph baseline or optional bounded nonlinear refinement can be added as an experiment later. Neither is required to implement the chosen MOVNS architecture.

## 5.4 CLI, results, and visualization

Expose mode; time budget(s); axis velocity/acceleration limits; velocity menu; initial/final states; seed; runtime/evaluation limits; archive/working-pool capacities; communication range/handshake/window; free-waypoint cap/workspace/step schedule; numerical tolerances. Reject incompatible flags early. Keep optimizer runtime distinct from mission time and per-agent flight budget in names/help text.

Write versioned metadata plus full solution decisions and trajectories, two-objective front, completion times, reached-task union, Δ/violation, contact intervals, diagnostics, and search logs. Prefer portable structured JSON plus array files over append-only pickle as the primary research artifact. Record source revision, schema/connector versions, dependencies, units, effective configuration, seed, elapsed computation, and counts. Existing pickle readers need an explicit legacy adapter.

Visualizations use actual time, show task visits versus free waypoints, velocity/acceleration histories, stopped waits, post-arrival stationary communication, active effective links, and staleness. Fronts are 2D reward versus mean completion time; Δ can color points but is not an axis implying a third objective. Plot contact and handshake intervals separately.

## 5.5 Documentation and release checklist

- Update README to the three modes, ignored collisions, flight-time budget, two objectives, and communication constraint.
- Replace removed-module references and obsolete sample commands; provide tiny checked instances so examples run.
- Update modeling/variables/formulation/neighborhood documents in the same implementation change that adopts their semantics.
- Publish meaningful test commands and a reproducible benchmark manifest.
- Document numerical validity policy, state-menu/free-waypoint restrictions, and difference from source KOP endpoint conventions.
- Retain the no-communication team baseline and single-agent reference mode.
- Check all exported fronts independently from stored trajectories.

## Milestone completion record

Each implementation milestone should record changed modules, validation commands/results, benchmark artifacts, known limitations, and remaining tasks. Do not mark a scientific stage complete merely because a smoke run produced a front. Code review should inspect objective directions, terminal budget accounting, velocity continuity, handshake interval merging, and propagation left limits explicitly.

## Outstanding defaults to confirm during implementation

No additional permission is needed to begin the staged implementation once requested. Model defaults requiring explicit documentation are: axis versus magnitude limits, endpoint velocities, exact passage versus a physical collection radius, workspace bounds, state-menu resolution, and free-waypoint cap. The proposed defaults are recorded in the model contract; changing one requires matching tests and benchmark metadata. Initial/final zero velocity and bounded workspace are recommendations, not decisions already supplied by the user.
