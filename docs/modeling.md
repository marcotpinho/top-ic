# Team KOP with Intermittent Communication — Modeling

This document describes the target research model. The implementation is being planned in [spec/](../spec/README.md); the foundation implements acceleration-aware trajectories; search stages are tracked in [implementation status](implementation.md).

## Research stages

1. Apply Multi-Objective Variable Neighborhood Search (MOVNS) to single-agent Kinematic Orienteering (KOP).
2. Extend the problem to multiple agents with shared reward accounting.
3. Add intermittent communication and freely positioned waypoints for rendezvous and motion shaping.

[KOP](https://arxiv.org/abs/2211.16837) supplies the motion-generation reference. The team, communication, and multiobjective extensions are part of this project. Free waypoints are enabled only in the third stage.

## Tasks, agents, and motion

Tasks are fixed 2D locations with nonnegative rewards. Each agent chooses which tasks to visit and in which order, starting at a common start and ending at a common destination. An explicit TASK visit collects its reward once for the team; repeated or shared TASK visits earn no additional reward. Task passage does not require stopping. A trajectory crossing without a TASK occurrence earns no reward.

Agents follow double-integrator dynamics: position changes with velocity, and velocity changes with bounded acceleration. Their velocities remain continuous; acceleration may change between motion pieces. A visit includes position and velocity, so task order alone does not specify a complete solution.

The proposed initial motion convention is KOP-compatible componentwise velocity and acceleration bounds. These are axis bounds, not bounds on Euclidean speed or acceleration magnitude. Initial velocity is configurable, with zero as the default. Final velocity is zero so that agents can remain stationary after arrival. Declared TASK visits must match fixed task coordinates; there is no physical reward-collection radius.

**Collisions are ignored in this version.** Agents may cross or occupy the same position. Obstacles, jerk constraints, and detailed vehicle energy models are outside the initial scope. These motion conventions and the remaining configurable defaults are recorded in the [model contract](../spec/00-model-contract.md).

## Flight-time budget and objectives

Each agent has a flight-time budget measured in seconds. Expenditure is elapsed time from mission start to final arrival, including travel and all waiting before arrival. Waiting is possible only at zero velocity; stopping requires feasible deceleration.

An agent stops consuming budget after final arrival, remains at the destination, and continues to communicate until the last agent arrives. Thus an early agent's terminal waiting affects communication but neither expenditure nor completion time. The mission horizon is the maximum individual completion time.

The ICC stage has three Pareto objectives:

- Maximize total team reward, counting each task once.
- Minimize average completion time, which is average budget expenditure.
- Minimize communication violation $V_c=\max(0,\Delta-T_c)$ for the configured $T_c$.

The single-agent and team KOP stages use the first two objectives only.

Path length and mission horizon are diagnostics. Flight-time expenditure is not a physical energy model. Individual budgets remain constraints; a low team average cannot offset an over-budget agent.

## Intermittent communication

Two agents communicate when they have remained continuously within Euclidean range $R$ for a handshake duration $\delta$. After the handshake they exchange data instantly while remaining in range. A genuine interruption resets the handshake. Initial handshakes and synchronization are assumed complete before departure.

Agents store and forward data. Simultaneously linked agents relay instantly through connected components; encounters at different times must form a chronological chain. For example, A meeting B before B receives C's data does not deliver that data to A.

Define $\Delta$ as the supremum of information staleness over the mission, including limiting peaks immediately before exchanges. A reported $T_c$ slice keeps solutions with $\Delta\le T_c$, equivalent to all-to-all information propagation in every full sliding window of that duration contained in the mission.

$V_c=\max(0,\Delta-T_c)$ is the third ICC search objective. All solutions within the bound tie at zero violation; physically valid candidates above the bound remain available as stepping stones. A separate dominated-solution archive preserves alternative search seeds using crowding distance; the Pareto archive itself uses epsilon-box dominance. A different $T_c$ requires a separate search.

Search guidance additionally records the peak age of each directed source–receiver information pair and the integrated excess age $\sum_{s\ne r}\int_0^T[A_{rs}(t)-T_c]_+\,dt$. These quantities help retain and revisit partially repaired, physically valid candidates whose global $\Delta$ has not yet changed. They do not alter $V_c$, feasibility, or the reported Pareto front. Meeting proposals are prioritized using the bottleneck time and spatial distance to range. A sampled comparison of unrefined and route-time-DP states measures when refinement helps or harms communication; a valid unrefined state is retained when it is better under the run's feasibility-first, then time/violation comparison.

No extra final-delivery requirement is imposed. A contact at the destination still needs its handshake unless it is a continuation of an already established link. If the mission is shorter than $T_c$, there is no full sliding window to enforce.

## Free waypoints and solution method

The communication stage adds actual visit positions that are not task locations. They can create meetings or shape motion and have no intrinsic reward, even when their coordinates coincide with a task. These waypoints are visited positions, not spline control points that the trajectory need not traverse.

MOVNS changes task selection/order/assignment, visit velocities, stopped waits, and, in the third stage, free positions and coordinated meetings. A deterministic connector constructs complete acceleration-feasible trajectories. Continuous contact extraction and temporal propagation then evaluate communication. Minimum-time connectors are a starting point; waiting and changed motion states allow communication-aware schedules.

A general nonlinear inner optimizer is optional refinement, not a mandatory part of every candidate evaluation. The baseline uses visit-level motion states and continuous trajectories rather than a uniform time-expanded workspace graph. See [neighborhood structures](neighborhood_structures.md), [variables](variables.md), and [mathematical formulation](math_formulation.md).

## Implementation status

See [implementation milestones](implementation.md) for supported stages, validation, and commands. The step 4 branch now implements continuous communication and free rendezvous waypoints; see the milestone record for supported numerical policies and limits.

Single-agent implementation: MOVNS and the five named KOP neighborhoods are available; see [step 2 status](implementation.md#step-2--single-agent-movns-kop). Team assignment operators are now implemented on the step 3 branch; communication is implemented on the step 4 branch.

Team implementation: individual time budgets, shared reward accounting, and cross-agent assignment moves are available; see [step 3 status](implementation.md#step-3--multi-agent-kop). Collision constraints remain ignored. Communication and FREE visits are enabled only in `team_kop_icc` mode.

## Step 4 implementation

`team_kop_icc` implements quartic range-contact extraction, maximal-interval handshake handling, initial synchronization, simultaneous connected-component relay, and vector-clock staleness with left limits. An independent reverse temporal-reachability oracle validates propagation. Near-multiple roots that cannot be resolved under the numerical policy are rejected rather than admitted as feasible.

Meetings reference preserved visit occurrences. A least-schedule difference-constraint solver detects positive cycles and adds stopped waits, charged until each agent's final arrival. Free positions are bounded by the configured workspace and per-agent visit cap. Five communication-stage operator families are `wait`, `meeting`, `duplicate_rendezvous`, `free_move`, and `free_remove`. Existing task and assignment families remain available.

The current ICC epsilon archive uses negative reward, mean completion time, and communication violation at the run's $T_c$. Valid motion and individual budgets determine archive eligibility; the reported reward–time front is its zero-violation slice. A separate bounded dominated-solution archive uses normalized crowding distance to preserve diverse search seeds. Full propagation is recomputed; pair-contact caching includes the mission horizon. Checkpointed incremental propagation is deferred.

Current ICC results use schema version 4 and include full routes, meetings, actual visit times, trajectories, raw/effective contacts, staleness traces, a three-objective archive, a dominated archive, accepted-front snapshots, and the zero-violation front at the configured $T_c$. Historical stage-4 files remain schema versions 2 or 3. ICC VND examines at most 120 candidates per family per pass by default; these are search restrictions, not completeness guarantees.
