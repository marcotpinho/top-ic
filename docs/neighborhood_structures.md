# Team KOP-ICC — MOVNS Neighborhood Structures

The current search rewrite is described in [TOP-CC-shaped rebuild](topcc-rebuild.md).
Implementation-status paragraphs below document the frozen pre-rebuild solver;
the model and named move definitions remain the design reference.

Target search design, following [modeling](modeling.md), [formulation](math_formulation.md), and the [implementation plans](../spec/README.md). Operators act on task/free visit occurrences, boundary velocities, stopped waits, and optional planned meetings. This replaces the earlier distance-based, constant-speed neighborhood assumptions.

## 1. Representation and invariants

A solution stores one ordered plan per agent. Each starts at START, ends at terminal END, and contains stable visit occurrence IDs. TASK positions are fixed; FREE positions are adjustable and enabled only in the communication stage. An agent can revisit a task and several agents can explicitly visit it; reward comes from the union of TASK IDs and is counted once globally. Incidental crossings earn no reward.

Each visit has a boundary velocity and nonnegative wait. Positive waits require zero velocity and feasible adjacent braking/acceleration. Final velocity is zero; terminal stationary presence through the mission horizon consumes no additional budget. Any task/depot indexing must remain independent from occurrence order.

Candidate construction produces complete continuous motion. Evaluation does not silently change task order. In current ICC search the runner deterministically refines each candidate's velocity states before passing the explicit refined solution to the evaluator; earlier-stage search still has a standalone refinement operator. Seeded shaking and deterministic construction/enumeration separate search randomness from trajectory evaluation.

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
| N12 | Duplicate-task rendezvous | Replace a duplicate TASK occurrence with an off-task FREE visit, optionally linking it to another agent's stopped task visit | Communication stage |
| N13 | Velocity DP refinement | Re-optimize every visit velocity on a fixed route over the finite state menu | Single KOP onward |
| N14 | Excursion / split-and-rejoin | Let one agent retain a short shared task subsequence while another bypasses it, with a moving rejoin proposed first | Communication stage |

IDs are proposed and supersede previous N1–N7 meanings; code enums should follow the new named families. Coordinate descent or continuous refinement may supplement N5/N10 after the baseline is validated.

For insertion between visits A and B, single/team modes enumerate the inserted visit's admissible velocity states while initially keeping A/B states fixed. ICC creates a structural edit and then runs the route velocity DP before scoring. Connection-time differences use the kinematic connector, not Euclidean detours. Reversing a subsequence requires reconstruction of directed motion; reversed old profiles are generally invalid.

N6 may preserve the team task set while changing mean completion time and individual budget utilization. N7 can reduce expenditure by removing an unnecessary wait, but communication must be reevaluated. A moving agent cannot gain a wait without first acquiring a zero-velocity visit state.

N8/N9 may require changing several agents at once. FREE visits have no intrinsic reward, and incidental task passage does not count. Propose initial meeting positions from trajectory midpoints/projections or bottleneck information, then explore deterministic directions and scales inside configured search bounds. These are candidate heuristics, not complete enumeration of continuous positions.

The historical N12 `duplicate_rendezvous` operator targets a task explicitly visited by at least two agents and changes one occurrence to FREE near the partner. It remains callable for reproducing old experiments but is no longer an enabled ICC search family: `remove` followed by `meeting` invite covers this search direction. A FREE occurrence never collects reward, even at task coordinates; the partner's retained TASK occurrence preserves the team's reward.

The current ICC runner visits every enabled family in the order listed below, subject to the candidate and wall-clock limits. Each family starts from an independent noisy ruin-and-recreate perturbation of the same selected base. Capped routing neighborhoods interleave per-agent candidate streams; excursion, meeting, and unlink interleave per-agent-pair streams. A fresh seeded shuffle changes the first agent or pair on every call, with the communication bottleneck pair first when known. Perturbation uses separate ruin-and-recreate moves.

N13 builds one layer per visit, enumerates heading/speed states (zero speed once), and connects adjacent layers using cached minimum-time kinematic segments. A left-to-right dynamic program stores the minimum accumulated connector time and predecessor for each state; backtracking yields the route's least flight time over that finite menu in $O(L S^2)$ connector lookups for $L$ visits and $S$ states. Starts, ends, positive-wait visits, and planned meeting endpoints retain their required states. Current ICC search folds this deterministic refinement into every candidate before full evaluation; single/team modes retain the explicit N13 operator. The DP gives a route travel-time optimum for a fixed sequence and menu, **not** a team completion-time or ICC optimum. N5 remains available for single/team modes; ICC omits it. Ties follow menu order. After a route edit a prefix cost table can be reused, but optimal predecessor choices before the edit may change during backtracking.

N14 matches shared split and rejoin anchors by task ID, even when their route indices differ. It bypasses up to five follower tasks between them, then proposes adding one or two cheap currently unreached tasks to that shortcut before the pure bypass candidate. A stopped-reunion fallback adds a planned meeting; the scheduler inserts waiting only if arrivals require it. The full evaluator admits excursion candidates when motion and budgets are valid, recording their $V_c$ as an objective. This bounded neighborhood is particularly aimed at convoy solutions; it does not claim to enumerate arbitrary split paths or guarantee an improving candidate from every seed.

## 3. Objectives and acceptance

The ICC epsilon archive uses $(-Q,\bar c,V_c)$; earlier stages retain two objectives. Strict dominance means no worse values in every coordinate and a strict improvement in at least one. Equal objective vectors do not dominate each other; deduplication is a separate policy.

Reject malformed motion, individual budget violations, and unresolved numerical validity from the front. Retain positive-violation physical solutions in the three-objective archive when nondominated. A separate bounded dominated-solution archive uses normalized crowding distance to preserve spread among otherwise valid solutions outside the epsilon front. It is a search reservoir, not a reported Pareto front.

Keep some structurally distinct equal-objective seeds when their timings/contact histories differ. A useful sequence of edits can pass through dominated states, so shaking and dominated-archive exploration complement front-based intensification. No general connectivity of the accepted-state search space is asserted.

## 4. Candidate evaluation pipeline

1. In ICC mode, refine the explicit velocity states of each candidate route with deterministic finite-menu DP, fixing endpoints, meeting stops, and positive-wait stops.
2. Check occurrence IDs, endpoint states, task references, wait validity, meeting references, and waypoint caps/bounds.
3. Apply safe flight-time lower bounds. Straight-line distance divided by a valid maximum speed is a lower bound, not a full budget check.
4. Reconstruct affected kinematic connections with deterministic state-based caching. Reassemble downstream times; verify complete motion continuously.
5. Verify each agent's final arrival against its time budget. Derive reached-task union and mean completion time.
6. When communication is enabled, extend terminal presence through the updated mission horizon, extract maximal range intervals continuously, and apply handshakes.
7. Compute information propagation and staleness supremum; classify three-objective archive/dominated-archive eligibility.
8. Update the ICC archive, search-seed metadata, and operator statistics.

Generate candidates lazily rather than allocating every neighbor. Safe screening must not rely on an unproved nonnegative insertion-time change, an unsigned/reversible cost model, or a distance-budget detour formula. Dropping tasks to repair a budget is a new candidate edit, not evaluation.

## 5. Locality and scheduling

Changing a boundary state generally changes inbound/outbound motion pieces. Even when geometry elsewhere is unchanged, different durations shift all downstream absolute times. A fixed position–velocity–time anchor preserves a suffix trajectory if local reconstruction succeeds, but it does not preserve information delivered into that suffix.

Stationary meeting scheduling can use difference constraints once connector durations and stopped visit states are fixed. Detect positive cycles; do not assume the synchronization graph is acyclic. The earliest feasible schedule is a deterministic constructor, not the entire search space. Explicit extra waits and retiming moves must remain available.

A longer requested connection duration is not automatically feasible for fixed nonzero endpoint velocities. Scaling time changes those velocities. Use a validated fixed-duration connector if introduced; otherwise adjust stopped waits or motion states.

Initially evaluate the full communication sweep. Later cache unchanged pair contacts and restart from a verified checkpoint. Update terminal intervals when the mission horizon changes, including pairs whose routes were not edited. Merging a modified contact can alter its start and handshake completion earlier than the edited piece, so derive invalidation from actual changed effective intervals.

There is no general small bound on the change in $\Delta$ from a small route edit. Adding effective links with all trajectories fixed cannot increase staleness; adding a planned rendezvous and changing timing does not inherit that guarantee.

## 6. MOVNS roles

Current ICC intensification visits remove, replace, assignment, reorder, insert, excursion, meeting, and unlink in that order. Duplicate-task removals/replacements and relocation are generated first within their families. Insertions keep the two cheapest positions per unreached task; replacements consider the five closest unreached tasks; relocation and tail exchange are similarly bounded. Every family starts from the same selected seed after an independent ruin-and-recreate perturbation. The order controls which families receive computation before a wall-time cap; it does not chain a candidate from one family into the next. Measure real operator costs and adjust this order through experiments.

Current perturbation chooses only route removal, contiguous sequence removal, or spatially related removal. It then rebuilds with seeded noise and stochastic choice among promising reward-per-detour insertions across agents. A task explicitly visited by another agent receives 15% of its reward in this construction score; the full evaluator still counts shared reward once. Ruin size grows with unsuccessful passes. The runner validates complete rebuilds from longest to shortest and can fall back to the ruined solution. This supports exploration but is not a completeness proof.

Initial solutions include direct low-time trajectories, reward-oriented constructions, alternative assignments, and, in the communication stage, cooperative synchronized seeds. A direct route must itself satisfy each time budget. If no known feasible seed exists, report that status rather than selecting from an empty archive.

The three-objective ICC archive and the dominated archive have separate capacities. Reset neighborhood search after a qualifying improvement and bound restarts/repair work. All initialization and candidate work counts toward computation limits. Log evaluations and connector/contact/propagation effort as well as wall time.

## 7. Optional crossover and bounded repair

Introduce crossover only after baseline neighborhoods pass validation. Preserve stable task/visit IDs and motion-state decisions; reconcile missing/dangling meeting references explicitly. Reconstruct affected motion, repair invalid stopped waits, and attempt bounded task/meeting adjustments for budget or schedule violations.

Repair may fail. Neither removing every task nor removing every planned meeting proves physical feasibility: the direct route may exceed the flight budget. Return structured failure instead of claiming guaranteed successful repair. Positive-violation but physically valid offspring can enter the three-objective archive or dominated reservoir.

## 8. Validation and hypotheses

- Verify endpoint preservation, velocity continuity, waits, reward union, and individual budgets after each operator.
- Audit duplicate candidates with full decision-state hashes; deduplicate overlaps rather than assert pairwise-disjoint neighborhoods.
- Compare cached/incremental motion and communication evaluation against a full reference on random edit sequences.
- Check deterministic enumeration/construction with fixed inputs and seeded shaking reproducibility.
- Test two-agent coordinated moves that succeed where a single-agent repair does not.
- Test task-only versus free-position meetings under equal computation budgets.
- Ablate selection, velocity, transfer, waiting, meeting, free-position, and compound moves.
- Report two-objective front quality, feasible-run rate, communication violation, accepted moves, and evaluation cost by family.

Expected improvements from each family are hypotheses to test. Changed velocity states and contact ordering can defeat simple objective-direction guarantees. Avoid carrying over constant-speed triangle-inequality, disjointness, reachability, or guaranteed-repair proofs without rederiving their assumptions.

## Implementation status

See [implementation milestones](implementation.md) for supported stages, validation, and commands. The step 4 branch now implements continuous communication and free rendezvous waypoints; see the milestone record for supported numerical policies and limits.

Single-agent implementation: MOVNS and the five named KOP neighborhoods are available; see [step 2 status](implementation.md#step-2--single-agent-movns-kop). Team assignment operators are now implemented on the step 3 branch; communication is implemented on the step 4 branch.

Team implementation: individual time budgets, shared reward accounting, and cross-agent assignment moves are available; see [step 3 status](implementation.md#step-3--multi-agent-kop). Collision constraints remain ignored. Communication and FREE visits are enabled only in `team_kop_icc` mode.

## Epsilon-dominance archive policy

Archive filtering uses epsilon-box dominance, never crowding distance. With ICC minimization objectives $f=(-Q,\bar c,V_c)$ and positive widths $\varepsilon_Q,\varepsilon_c,\varepsilon_V$, floor the first two coordinates and set the third box to zero for $V_c=0$ or $1+\lfloor V_c/\varepsilon_V\rfloor$ otherwise. Earlier stages omit the third coordinate. Retain nondominated boxes and one representative per box, chosen by minimum squared normalized distance to its lower corner; objective values and full decision keys break ties deterministically. Flooring also applies to negative reward coordinates.

Defaults are `eps_reward=1.0` reward unit and `eps_time=0.1` second. ICC `eps_violation` defaults to one second and can be overridden explicitly. If capacity is exceeded, all widths double deterministically. Saved statistics record effective widths and coarsening count. This is an approximate epsilon front, not a promise to retain every exact Pareto point.

## Step 4 implementation

`team_kop_icc` implements quartic range-contact extraction, maximal-interval handshake handling, initial synchronization, simultaneous connected-component relay, and vector-clock staleness with left limits. An independent reverse temporal-reachability oracle validates propagation. Near-multiple roots that cannot be resolved under the numerical policy are rejected rather than admitted as feasible.

Meetings reference preserved visit occurrences. A least-schedule difference-constraint solver detects positive cycles and adds stopped waits, charged until each agent's final arrival. Free positions are bounded by the configured workspace and per-agent visit cap. The enabled ICC families, in evaluation order, are `reorder`, `insert`, `remove`, `replace`, `assignment`, `excursion`, `meeting`, `duplicate_rendezvous`, and `unlink`. Older `wait`, `free_move`, and `free_remove` are callable for historical experiments but disabled as independent ICC families. `meeting` targets the time reported by the staleness bottleneck, uses existing stopped visits when possible, projects guest FREE visits toward host stops, and retimes only linked endpoints. `duplicate_rendezvous` deterministically reprojects redundant task stops. `unlink` removes a meeting, FREE visit, or explicit wait; solo FREE/wait removals are assigned to one canonical pair stream to avoid duplicate proposals. Perturbation uses only route, sequence, and related removal followed by noisy recreation. Every family starts from its own shake of the same selected base; communication repair can follow routing changes through later archive selection, not within the same iteration.

The current ICC epsilon archive uses negative reward, mean completion time, and violation at the configured $T_c$. Valid motion and individual budgets determine archive eligibility; the reported reward–time front is the zero-violation slice. A separate bounded dominated-solution archive uses normalized crowding distance to preserve diverse search seeds. Full propagation is recomputed; pair-contact caching includes the mission horizon. Checkpointed incremental propagation is deferred.

Current ICC results use schema version 4 and include full routes, meetings, actual visit times, trajectories, raw/effective contacts, staleness traces, a three-objective archive, a dominated archive, accepted-front snapshots, and zero-violation front indices. Historical stage-4 files remain schema versions 2 or 3. The search cycles through unexplored front or dominated members, alternating reward and violation ranking. Within an iteration, every neighborhood shakes the same selected archive member independently and evaluates up to 120 candidates per family by default, adding every retained epsilon-nondominated result to the archive. These are search restrictions, not completeness guarantees.
