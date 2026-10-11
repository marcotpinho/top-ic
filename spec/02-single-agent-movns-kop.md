# Step 2: single-agent MOVNS for KOP

## Scope and dependencies

Requires Step 1 gates. Set M=1, communication disabled, FREE visits disabled. Optimize `(-reward, completion_time)` under one time budget. For communication diagnostics Δ=0 by convention. Use the same motion connector for MOVNS and comparison algorithms.

## 2.1 Evaluation

- Construct the trajectory deterministically from stored task order, visit states, and valid waits.
- Verify endpoints and task passage; compute actual completion time and budget feasibility.
- Count rewards by physical task IDs reached, including incidental crossings under the contract. Use bounding-box filtering and root/position checks for polynomial-piece passage; dense sampling is diagnostic only.
- Return immutable objectives and validity. Never hide a budget violation by dropping tasks inside evaluation.
- Lower-bound rejection may use straight-line distance divided by the maximum attainable speed; with axis-box limits the Euclidean speed bound is √2 v_axis_max. A tighter direction-dependent bound is possible. A bound must not overestimate the minimum duration or assume insertion cost is nonnegative when boundary-state choices change.

## 2.2 Initialization and feasible seeds

Construct a direct start-to-end seed. If it exceeds the budget, report no known feasible instance rather than attempting empty archive selection. An empty task set still requires reaching the destination.

Add greedy reward-per-additional-time seeds and time-focused/alternative-heading seeds. Resolve zero/negative insertion cost ratios explicitly, and break ties by fixed task/position/state order. Include the low-time zero-reward solution if nondominated. Seed the archive before neighborhood enumeration.

## 2.3 Neighborhoods

Implement lazy ordered generation:

| Move | Decisions changed | Reconstruction |
|---|---|---|
| Insert | Add unvisited task; enumerate a bounded state menu | Replace predecessor→successor by two connections |
| Remove | Remove one task occurrence | Reconnect predecessor→successor |
| Replace | Swap task for unvisited task | Rebuild its adjacent connections |
| Relocate / swap | Change order | Rebuild changed connections |
| Segment reversal | Reverse visit order | Reconstruct directed motion; do not reuse reversed costs |
| Velocity state | Change heading/speed at one visit | Reconstruct inbound and outbound motion |
| Wait decrease | Reduce unnecessary stopped dwell | Reassemble downstream times |

Wait insertion is not necessary for the no-communication baseline but representation must support it for Step 4. Shaking combines several edits with seeded random choices. Candidate-list pruning is configurable and must be relaxed during diversification; measure its effect rather than claim completeness.

## 2.4 MOVNS and archive

Modify `src/runner.py`, `src/operators.py`, `src/archive.py`, and `Solution.dominates`:

- All Pareto coordinates use minimization; strict dominance requires no worse values and at least one strict improvement. Equal objectives never mutually dominate.
- Archive contains motion/budget-feasible nondominated solutions only; capacity handling uses two-objective crowding or an explicitly documented ε policy.
- Keep structural duplicates and objective-equal alternatives separate. Store representative trajectories, not just score tuples.
- Select seeds using objective diversity/exploration state; remove RSSI selection and inverse-score calculations.
- Run VND over the neighborhood schedule; reset neighborhood index on a qualifying improvement. Define archive improvement as a new retained objective region, with deterministic handling of ties.
- Increase shaking intensity after unsuccessful passes; use bounded restarts when all archive seeds are explored. Initial neighborhoods and repair work count toward runtime/evaluation limits.
- Emit moves generated, screened, constructed, valid, accepted, connector failures, cache hits, and time by stage.

Optional crossover follows only after a correct MOVNS baseline. Offspring repair is explicit, must terminate under a bounded work budget, and must preserve a feasible direct route; otherwise return repair failure.

## 2.5 Candidate pipeline and reproducibility

Use cheap structural checks, safe bounds, connector reconstruction, full trajectory checks, reward/time scoring, and archive update in that order. Do not run a general nonlinear inner optimizer by default. Additional state refinement is an operator producing another candidate.

Use one explicitly passed RNG. Deterministic enumeration and fixed evaluation/iteration budgets support repeatable runs; wall-clock stops are for practical runtime experiments and may vary. Cache failures only when they are deterministic mathematical failures under the connector's documented domain.

## 2.6 Validation and exit gate

- Exhaustively enumerate task subsets/orders and state menus for very small cases to obtain the exact finite-menu two-objective front.
- Check dominance/equality/capacity, initial archive insertion, zero reward, zero tasks, tight budgets, and seed reproducibility.
- Verify every archived trajectory through a separate validator.
- Implement a KOP-inspired LNS baseline using identical bounds, boundary states, state menu, connector, and evaluator. Label altered endpoint conventions and multiobjective adaptations. A reward-only fixed-budget comparison can separately match the source KOP objective; do not compare its scalar output directly as a complete Pareto front.
- Compare MOVNS and LNS under equal wall time and, separately, equal evaluation counts, across multiple seeds and budget tightness levels. Report reward, time, feasibility, front quality, and effort.

Exit: single-agent CLI runs, valid finite-menu fronts on tiny instances, correct objective direction, no unreported repair mutations, and an initial fair benchmark. Superior performance is an empirical question, not a prerequisite for correct implementation.
