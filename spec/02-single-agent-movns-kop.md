# Step 2: single-agent MOVNS for KOP

## Scope and dependencies

Requires Step 1 gates. Set M=1, communication disabled, FREE visits disabled. Optimize `(-reward, completion_time)` under one time budget. For communication diagnostics Δ=0 by convention. Use the same motion connector for MOVNS and comparison algorithms.

## 2.1 Evaluation

- Construct the trajectory deterministically from stored task order, visit states, and valid waits.
- Verify endpoints and task passage; compute actual completion time and budget feasibility.
- Count rewards by task IDs named by explicit TASK occurrences. Check that the continuous trajectory passes through every declared visit; incidental task crossings earn no reward. Dense sampling is diagnostic only.
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
- Archive contains motion/budget-feasible nondominated solutions only; filtering uses two-objective epsilon-box dominance; capacity handling deterministically coarsens box widths and records the effective epsilon. Crowding distance is not used.
