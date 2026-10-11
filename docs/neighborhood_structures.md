# Team KOP-ICC — MOVNS Neighborhood Structures

Target search design, following [modeling](modeling.md), [formulation](math_formulation.md), and the [implementation plans](../spec/README.md). Operators act on task/free visit occurrences, boundary velocities, stopped waits, and optional planned meetings. This replaces the earlier distance-based, constant-speed neighborhood assumptions.

## 1. Representation and invariants

A solution stores one ordered plan per agent. Each starts at START, ends at terminal END, and contains stable visit occurrence IDs. TASK positions are fixed; FREE positions are adjustable and enabled only in the communication stage. An agent can revisit a task and several agents can reach it; reward is derived from actual trajectory passage and counted once globally.

Each visit has a boundary velocity and nonnegative wait. Positive waits require zero velocity and feasible adjacent braking/acceleration. Final velocity is zero; terminal stationary presence through the mission horizon consumes no additional budget. Any task/depot indexing must remain independent from occurrence order.

Candidate construction produces complete continuous motion. Evaluation does not silently change task order or optimize stored decisions. Seeded shaking and deterministic construction/enumeration separate search randomness from trajectory evaluation. Optional refinement and crossover are explicit operators, not hidden evaluator behavior.

Canonical keys include motion states, waits, free positions, meeting references, and any stored duration/profile decisions. Only identical agents may be reordered, with all references remapped. Heading is irrelevant for a zero velocity and is deduplicated. Task order alone is not a complete cache key.

## 2. Neighborhood families and staged availability

| ID | Move | Modified decisions | Available stage |
|---|---|---|---|
| N1 | Insert task | Task selection, occurrence position, boundary velocity | Single KOP onward |
| N2 | Remove task visit | Selection/order and adjacent connection | Single KOP onward |
| N3 | Replace task | One task for another; enumerate replacement state | Single KOP onward |
| N4 | Reorder | Relocate, swap, or reverse a visit subsequence | Single KOP onward |
| N5 | Velocity state | Heading/speed at one visit | Single KOP onward |
| N6 | Transfer/exchange | Visits or subsequences across agents | Team KOP onward |
| N7 | Wait/stop | Stopped dwell and, when needed, visit velocity | Communication stage |
| N8 | Meeting link/unlink | Planned meeting between existing stopped visits | Communication stage |
| N9 | Free rendezvous insertion | Free visits, positions, stopped states, joint timing | Communication stage |
| N10 | Free-position/timing change | Move/retime one free visit or a coordinated pair | Communication stage |
| N11 | Meeting/free-visit removal | Remove redundant meetings/visits and reconstruct | Communication stage |

IDs are proposed and supersede previous N1–N7 meanings; code enums should follow the new named families. Coordinate descent or continuous refinement may supplement N5/N10 after the baseline is validated.

For insertion between visits A and B, enumerate the inserted visit's admissible velocity states while initially keeping A/B states fixed. Connection-time differences use the kinematic connector, not Euclidean detours. Reversing a subsequence requires reconstruction of directed motion; reversed old profiles are generally invalid.

N6 may preserve the team task set while changing mean completion time and individual budget utilization. N7 can reduce expenditure by removing an unnecessary wait, but communication must be reevaluated. A moving agent cannot gain a wait without first acquiring a zero-velocity visit state.

N8/N9 may require changing several agents at once. FREE visits have no intrinsic reward, but incidental task passage still counts. Propose initial meeting positions from trajectory midpoints/projections or bottleneck information, then explore deterministic directions and scales inside configured search bounds. These are candidate heuristics, not complete enumeration of continuous positions.

## 3. Objectives and acceptance

The feasible archive uses only $(-Q,\bar c)$. Strict dominance means no worse values in both coordinates and a strict improvement in at least one. Equal objective vectors do not dominate each other; deduplication is a separate policy.

Reject malformed motion, individual budget violations, and unresolved numerical validity from the feasible front. Maintain a bounded separate working pool for otherwise valid communication-infeasible candidates, prioritizing $\max(0,\Delta-T_c)$ and preserving objective/structural diversity. Feasible solutions can use lower $\Delta$ as a tie-break or seed-selection preference; it is never a third crowding coordinate or archive level.

Keep some structurally distinct equal-objective seeds when their timings/contact histories differ. A useful sequence of edits can pass through dominated or communication-infeasible states, so shaking and working-pool exploration complement archive-based intensification. No general connectivity of the accepted-state search space is asserted.

## 4. Candidate evaluation pipeline

1. Check occurrence IDs, endpoint states, task references, wait validity, meeting references, and waypoint caps/bounds.
2. Apply safe flight-time lower bounds. Straight-line distance divided by a valid maximum speed is a lower bound, not a full budget check.
3. Reconstruct affected kinematic connections with deterministic state-based caching. Reassemble downstream times; verify complete motion continuously.
4. Verify each agent's final arrival against its time budget. Derive reached-task union and mean completion time.
5. When communication is enabled, extend terminal presence through the updated mission horizon, extract maximal range intervals continuously, and apply handshakes.
6. Compute information propagation and staleness supremum; classify archive/working-pool eligibility.
7. Update two-objective archive, search-seed metadata, and operator statistics.

Generate candidates lazily rather than allocating every neighbor. Safe screening must not rely on an unproved nonnegative insertion-time change, an unsigned/reversible cost model, or a distance-budget detour formula. Dropping tasks to repair a budget is a new candidate edit, not evaluation.

## 5. Locality and scheduling

Changing a boundary state generally changes inbound/outbound motion pieces. Even when geometry elsewhere is unchanged, different durations shift all downstream absolute times. A fixed position–velocity–time anchor preserves a suffix trajectory if local reconstruction succeeds, but it does not preserve information delivered into that suffix.

Stationary meeting scheduling can use difference constraints once connector durations and stopped visit states are fixed. Detect positive cycles; do not assume the synchronization graph is acyclic. The earliest feasible schedule is a deterministic constructor, not the entire search space. Explicit extra waits and retiming moves must remain available.

A longer requested connection duration is not automatically feasible for fixed nonzero endpoint velocities. Scaling time changes those velocities. Use a validated fixed-duration connector if introduced; otherwise adjust stopped waits or motion states.

Initially evaluate the full communication sweep. Later cache unchanged pair contacts and restart from a verified checkpoint. Update terminal intervals when the mission horizon changes, including pairs whose routes were not edited. Merging a modified contact can alter its start and handshake completion earlier than the edited piece, so derive invalidation from actual changed effective intervals.

There is no general small bound on the change in $\Delta$ from a small route edit. Adding effective links with all trajectories fixed cannot increase staleness; adding a planned rendezvous and changing timing does not inherit that guarantee.

## 6. MOVNS roles

VND intensifies using a configurable deterministic schedule. Start with velocity-state/reorder moves, then selection moves, then inter-agent assignment, and finally timing/meeting/free-position moves when enabled. Measure real operator costs and adjust this order through experiments.

Shaking applies seeded compound edits, increases intensity after unsuccessful passes, and can jointly perturb several agents. Candidate lists restrict intensification optionally; diversification can relax those restrictions. This supports exploration but is not a completeness proof.

Initial solutions include direct low-time trajectories, reward-oriented constructions, alternative assignments, and, in the communication stage, cooperative synchronized seeds. A direct route must itself satisfy each time budget. If no known feasible seed exists, report that status rather than selecting from an empty archive.

The two-objective nondominated archive and the communication working pool have separate capacities. Reset neighborhood search after a qualifying improvement and bound restarts/repair work. All initialization and candidate work counts toward computation limits. Log evaluations and connector/contact/propagation effort as well as wall time.

## 7. Optional crossover and bounded repair

Introduce crossover only after baseline neighborhoods pass validation. Preserve stable task/visit IDs and motion-state decisions; reconcile missing/dangling meeting references explicitly. Reconstruct affected motion, repair invalid stopped waits, and attempt bounded task/meeting adjustments for budget or schedule violations.

Repair may fail. Neither removing every task nor removing every planned meeting proves feasibility: the direct route may exceed the flight budget, and opportunistic contacts may still violate recurrence. Return structured failure instead of claiming guaranteed successful repair. Communication-infeasible but physically valid offspring may enter the separate working pool.

## 8. Validation and hypotheses

- Verify endpoint preservation, velocity continuity, waits, reward union, and individual budgets after each operator.
- Audit duplicate candidates with full decision-state hashes; deduplicate overlaps rather than assert pairwise-disjoint neighborhoods.
- Compare cached/incremental motion and communication evaluation against a full reference on random edit sequences.
- Check deterministic enumeration/construction with fixed inputs and seeded shaking reproducibility.
- Test two-agent coordinated moves that succeed where a single-agent repair does not.
- Test task-only versus free-position meetings under equal computation budgets.
- Ablate selection, velocity, transfer, waiting, meeting, free-position, and compound moves.
- Report two-objective front quality, feasible-run rate, communication violation, accepted moves, and evaluation cost by family.

Expected improvements from each family are hypotheses to test. Incidental reward collection, changed velocity states, and contact ordering can defeat simple objective-direction guarantees. Avoid carrying over constant-speed triangle-inequality, disjointness, reachability, or guaranteed-repair proofs without rederiving their assumptions.

## Implementation status

See [implementation milestones](implementation.md) for supported stages, validation, and commands. Communication and free-waypoint sections describe the later target extension, not completed functionality.

Single-agent implementation: MOVNS and the five named KOP neighborhoods are available; see [step 2 status](implementation.md#step-2--single-agent-movns-kop). Team and communication operators remain later-stage functionality on this branch.

## Implemented epsilon archive policy

For minimization vector $f=(-Q,\bar c)$, define box $b_j=\lfloor f_j/\varepsilon_j\rfloor$. Box dominance requires no worse box coordinates and at least one strict improvement. Within one box retain the trajectory nearest its normalized lower corner, with deterministic objective/decision ties. Defaults are $\varepsilon_Q=1$ reward unit and $\varepsilon_c=0.1$ seconds. If capacity is exceeded, double both widths until the approximate box front fits and record effective widths. Crowding-distance truncation is not used.
