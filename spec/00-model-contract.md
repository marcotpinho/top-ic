# Model contract

## 1. Inputs and units

Tasks have stable IDs, 2D coordinates, and nonnegative rewards. Start and destination are distinct semantic entities even when their coordinates coincide; depot reward is zero. Every agent starts at the common start at time zero and terminates at the common destination. Each has a flight-time budget B_m in seconds. Initially use identical agents, retaining indexed input fields for future heterogeneous instances.

Motion obeys `dp/dt = v`, `dv/dt = a`. Positions, velocities, and accelerations are continuous-valued. Velocity is continuous across pieces; acceleration may jump. No jerk limit, gravity, drag, motor model, obstacles, or collision constraints are included in the initial implementation. Co-location and crossing are legal, including at rendezvous and depots.

Recommended default: KOP-compatible componentwise bounds `|v_x|, |v_y| ≤ v_axis_max` and `|a_x|, |a_y| ≤ a_axis_max`. These are box bounds, not Euclidean magnitude bounds. They permit diagonal magnitudes up to √2 times the component limit. Name and serialize bounds accordingly. If magnitude limits are desired later, use a different connector or documented conservative axis limits; do not reuse the same physical labels while changing feasible motion.

Recommended default: zero initial and final velocity, configurable in the instance. The source-paper comparison must use matching boundary states, even if that requires a separate benchmark configuration.

## 2. Visits and motion states

A visit occurrence has a stable visit ID, kind, position, boundary velocity, and nonnegative wait duration. Kinds are START, TASK, FREE, END. TASK references a fixed task ID; FREE stores its own coordinates and has no intrinsic reward. Arrival times are derived from motion durations and waits, not independent unconstrained values.

Initially select visit velocities from deterministic finite heading/speed menus, including zero. Deduplicate zero-speed states regardless of heading. This is a discretization of visit states, not of the entire workspace or time axis. Continuous velocity refinement can be added later as an explicit neighborhood.

One agent may stop or pass through a task. Waiting at a visit is permitted only with zero boundary velocity. Agents cannot pause with nonzero velocity or instantaneously stop. A move requesting a wait must also change the visit's velocity to zero and reconstruct adjacent motion.

Repeated task-location visits are representable by separate occurrences. In the single-agent and team stages, prefer unique visits for reward selection. The communication stage allows repeats and shared visits for meetings. Arrival at the terminal END occurrence ends budget consumption; trajectories may not leave the destination after termination. Recommended default: do not schedule an intermediate destination visit followed by departure. When start and destination coordinates coincide, the initial START occurrence does not count as final arrival; a direct empty route can terminate at time zero, while a reward-collecting route terminates on its final return.

## 3. Budget and objectives

Let c_m be final arrival time, including every wait before arrival. Enforce `c_m ≤ B_m`; define mission horizon `T = max_m c_m`. No total-team substitute can replace the individual constraints.

The expenditure objective is `mean_completion_time = sum(c_m)/M`, and minimization-form objectives are `(-total_reward, mean_completion_time)`. For one agent this is `(-reward, completion_time)`. Moving duration, waiting duration, path length, and mission horizon are diagnostics, not additional Pareto objectives.

After arrival an agent has position equal to destination and velocity/acceleration zero until T. This stationary extension contributes to communication only; it adds no expenditure. Earlier robots remain communication participants and retain/forward information.

Reward is the sum over task locations actually reached by any trajectory before termination, counted once globally. Recommended default: exact point passage in the mathematical model, with a separately configured numerical position tolerance. Explicit visits guarantee passage; incidental task crossings should also count if discovered by the trajectory evaluator. Numerical tolerance must not become an undocumented physical collection radius. A designated reward owner is optional bookkeeping, not the source of the objective. Coincident task coordinates require explicit distinct IDs and a documented collection rule; default is collecting all tasks at that coordinate.

## 4. Communication semantics

Inputs are range R, handshake time δ ≥ 0, and recurrence bound T_c > 0. Contacts are maximal closed time intervals on [0,T] where Euclidean separation is at most R. Merge continuous contact across trajectory-piece boundaries before applying a handshake. A genuine interruption resets it.

Agents complete initial synchronization and handshakes before departure. An initial maximal contact [0,e] is active over its entirety. Later contact [s,e] becomes usable on [s+δ,e] if e-s ≥ δ. Equality yields an instantaneous usable link. δ=0 also permits isolated range-touch events.

At any instant, all agents in an active-link connected component exchange information instantaneously. Information can be stored and forwarded later. Simultaneous multi-hop relay is allowed; chronological order of non-simultaneous contacts matters.

Let h_nm(t) be the latest source timestamp from m available at n. Initialize all entries at zero and set diagonal entries to current time during propagation. Define Δ as the supremum over [0,T] of `t-h_nm(t)` for m≠n; define Δ=0 when M=1. Record left limits before communication updates, not only values after updates.

Require Δ≤T_c. Equivalently, every full window [t,t+T_c] contained in [0,T] supports all-to-all time-respecting journeys. If T<T_c, the full-window requirement is vacuous and Δ≤T_c follows from synchronization. No separate final-delivery requirement is added. Co-location at final arrival does not waive a pending handshake.

## 5. Search policy

Reject malformed trajectories, unresolved numerical validity, and budget-infeasible candidates from the feasible archive. Permit a separate bounded working pool of motion/budget-feasible candidates that violate communication, ordered first by `max(0,Δ-T_c)`, then by the two objectives/diversity. Do not penalize physical objectives or add Δ as a third archive coordinate.

Among objective-equal feasible candidates, smaller Δ can prefer a representative or search seed. Preserve a bounded set of structurally different objective-equal seeds outside the Pareto archive if useful; otherwise identical scores may erase different future communication opportunities. Search preference is not Pareto dominance.

Use canonical, deterministic keys and seeded RNG for shaking/selection. Only exchange agent identities when every relevant parameter and boundary state is identical; remap meeting references when canonicalizing. Do not promise all neighborhoods are disjoint or the feasible search space is connected without evidence.

## 6. Free-waypoint scope

Enable FREE visits only in the communication stage. Recommended default: positions inside an explicit bounded workspace enclosing tasks and depots, adjustable free-waypoint count limit per agent, and scheduled neighborhood step sizes. These are algorithmic restrictions, not proofs that optimal meetings lie inside the task bounding box or under the chosen count cap. Report the limits and sensitivity experiments.

At least one coordinated move must insert/move a pair of rendezvous visits and adjust both agents' motion states/timing together. Stationary planned meetings are a constructive mechanism; all valid moving contacts still count.

## Archive policy decision

Confirmed during implementation: use epsilon-box dominance for reward and mean completion time, not crowding-distance filtering. Positive configurable epsilon widths and any deterministic capacity-driven coarsening are recorded in run metadata. Delta remains outside the archive coordinates.
