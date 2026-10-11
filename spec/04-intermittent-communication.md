# Step 4: intermittent communication and free waypoints

## Scope and dependency order

Requires team-KOP gates. Implement continuous communication verification before communication-guided search. Then add stopped waiting/rendezvous at task locations, and finally FREE visits and coordinated movable rendezvous. All three substeps belong to this implementation stage.

## 4.1 Continuous contact extraction

Add `src/contacts.py`. Extend each completed trajectory with a stationary destination piece through T; M=1 is handled without pair extraction.

For each pair, sweep overlapping piece intervals in chronological order. At a shared local time origin, relative position has form `q(τ)=c+bτ+dτ²`. Range membership is the sign of the polynomial `g(τ)=q(τ)·q(τ)-R²`, of degree at most four.

Implement a robust reference interval solver:

1. Normalize local time/coefficients, reduce truly negligible leading degree under a documented scale policy, and recognize constant/identically-zero cases.
2. Find derivative critical points and real roots inside the overlap, using bracketing on monotone intervals plus checks for even-multiplicity tangent roots. Avoid relying only on sign changes or blindly accepting complex-root approximations.
3. Partition by endpoints/roots; classify interior sign and explicitly retain isolated touch events.
4. Verify residuals and reconstruct physical range separation near boundaries; return uncertainty if classification cannot meet the configured tolerances.
5. Merge adjacent physical contact intervals across motion switches before applying the handshake. Do not bridge a proven out-of-range gap merely because it is short.

Use scale-aware root/residual/time tolerances. Conservative handling of unresolved gaps/durations prevents false feasibility; record uncertainty rather than claim symbolic exactness. Dense trajectory sampling is a plotting/cross-check tool and cannot certify handshake continuity.

Apply the initial-handshake exception; discard later contacts shorter than δ; retain equality contacts as point links. Serialize both raw and effective intervals for debugging.

Tests: constant range; disjoint; crossing; tangency; multiple intervals on one overlap; zero acceleration reduction to quadratic; exact range; switching-piece continuity; below/equal/above handshake length; interrupted handshake; δ=0; initial contact shorter than δ; early arrival at end.

## 4.2 Latest-information sweep

Add `src/communication.py`. Use effective-interval endpoints plus 0,T as breakpoints. Maintain M×M latest-source timestamp matrix H with all entries initially zero.

At each segment between breakpoints, the active graph is constant. For each component, source timestamps from members advance continuously to current time; external-source timestamps are the componentwise maxima of held information. Isolated agents advance their own diagonal timestamps. At the next breakpoint:

- Advance the preceding steady graph to the left limit and record staleness supremum there.
- Activate all links present at the exact breakpoint, including those ending/starting there and zero-length links.
- Exchange componentwise maxima simultaneously across each whole connected component, after refreshing diagonal entries to the breakpoint time.
- Record post-update staleness and determine the graph active over the next open segment.

The record immediately before T matters even if final exchange drops all ages to zero. Store bottleneck source/receiver/time and preceding contacts for move prioritization. Δ does not depend on T_c; a fixed trajectory evaluation can be reused across threshold sweeps.

Tests: two-agent sawtooth with unattained peak; A→B then B→C versus reversed order; simultaneous chain relay independent of edge iteration order; continuous steady component; disappearing/appearing edges at one instant; partial components; no post-initial contacts; M=1; T<T_c; terminal handshake; equality boundary Δ=T_c. Cross-check tiny schedules with an independently implemented temporal-reachability oracle over departure/query times and event left limits.

Gate: full continuous reference evaluator validated before any incremental implementation. Revise old complexity claims based on actual root extraction/sweep work rather than copying constant-speed claims.

## 4.3 Archive and search guidance

Feasible archive remains two-dimensional. Motion/budget-feasible solutions with communication violations enter a bounded separate working pool. Select infeasible seeds by violation first, with objective/structural diversity and bounded exploration. Feasible seeds use the Pareto front and may prefer lower Δ for ties or selection. Report archive and working pool separately.

Check that Δ never becomes a crowding coordinate, objective penalty, or epsilon archive level. Do not discard an entire search region because one proposed rendezvous increases staleness: changed timing can remove earlier contacts even when adding a planned link.

## 4.4 Waiting and planned task-location rendezvous

Allow waits at stopped visits, including the start before departure; all such waits count until final arrival. Add link/unlink, wait adjustment, stop-state insertion, and coordinated two-agent rendezvous moves.

For a stationary planned meeting, two zero-velocity visits within R need continuous presence overlap ≥δ. Meeting references use stable occurrence IDs. The first deterministic scheduler may compute earliest valid waits for fixed connector durations. This scheduling subproblem can use lower-bound difference constraints; cycles require explicit detection rather than assuming a DAG. Travel duration and stopping states must already be fixed for that scheduling call.

Earliest scheduling is a constructor, not the only searched schedule. Store extra waits as decisions and allow moves delaying/repositioning contacts. Drop stale meeting references on route edits or jointly repair them; never turn arrival at a nonzero velocity into stationary presence.

Start with cooperative low-reward seeds: all agents follow identical direct motion when identical parameters make that feasible, yielding continuous connectivity, then insert tasks. Record seeds that fail for heterogeneous agents without claiming general feasibility.

## 4.5 Free waypoint representation and search

Enable FREE visits only now. They contain position, boundary velocity, optional stopped dwell, and meeting references. Generate positions continuously; do not snap them to tasks or silently replace them by spline control points that are not visited.

Neighborhoods:

- Insert a coordinated pair of free visits on two routes at a common candidate meeting position, initially with zero velocity and sufficient handshake dwell.
- Propose midpoint/projection positions from existing trajectories near a bottleneck time; these are heuristics, not exhaustive choices.
- Move one free visit or a paired rendezvous using deterministic direction menus and shrinking/expanding step sizes.
- Adjust rendezvous timing and stopped waits together; change free-visit velocity for moving encounters when supported.
- Remove a free visit, remove a meeting, merge redundant meetings, or exchange meeting partners, reconstructing all affected motion.
- Use compound group shaking to bypass dominated intermediate states.

Use explicit workspace bounds and per-agent free-visit caps. Test several caps/step sizes; waypoint caps are algorithmic restrictions. Only physical visits collect task rewards, including incidental task passage. FREE itself has zero reward.

A candidate is complete only after deterministic connector construction and scheduling. If local repair cannot connect fixed boundary states, enlarge its neighborhood or reject that attempt; failure is not a proof of global infeasibility.

## 4.6 Locality and evaluation cost

Initially recompute the full propagation sweep for every assembled candidate. Cache motion connections and unchanged pair contacts. A horizon change affects terminal stationary intervals even for unedited agents; update every affected pair.

Later, recompute only changed trajectories/pairs and restart propagation from a validated checkpoint before the earliest changed effective link. Contact merging can move a handshake start earlier than the directly edited piece; derive invalidation from the merged interval, not merely the edited visit time. Checkpoints include H, steady graph, previous peak, and active intervals; match against full recomputation on randomized candidate edits.

Preserving position/velocity/time at an anchor preserves the geometric suffix, not the information state. Continue propagation verification downstream. No blanket promise of bounded Δ change from a small edit is valid.

Optional continuous refinement is a separate explicit move applied to selected candidates. It may optimize free positions/timing within a bounded deterministic work budget, but never bypasses the final continuous verifier.

## Exit gate

Feasible fronts contain only motion/budget/communication-verified solutions. Tests cover moving/stationary/terminal links, zero-length contacts, simultaneous relay, uncertainty handling, waits charged correctly, repeated visits, free positions, and equal-objective search guidance. Demonstrate an instance where a free rendezvous improves feasibility or the two-objective front relative to task-only meetings, using equal search effort and multiple seeds.

## Implementation record

Implemented on `implementation/step4-intermittent-communication`; see [milestones](../docs/implementation.md) and [experiment report](../docs/experiments-icc.md). Numerical contact extraction, full clock sweep, stopped-meeting schedule, free positions, four new operator families, guidance pool, and portable data export are available. Pair caches include horizon changes; checkpointed incremental sweeps are deferred as planned.

70 correctness tests pass. The user’s ten-run budget is respected: three Tc settings, new-family singleton ablations, and paired full/task-only seeds. Independent data validators check all exported fronts and banks. The dense benchmark did not demonstrate a free-waypoint performance advantage; a controlled fixed-route fixture demonstrates spatial feasibility improvement only. Broader statistical/instance-general benefit remains an empirical research question, not an implementation claim.
