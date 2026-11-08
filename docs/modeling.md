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

The proposed initial motion convention is KOP-compatible componentwise velocity and acceleration bounds. These are axis bounds, not bounds on Euclidean speed or acceleration magnitude. Initial velocity is configurable and nonzero. Missing or zero initial states are converted to 10% of the directional axis limit, using the nearest 45-degree heading from START toward END (east when depots coincide). Arrival velocity is nonzero; stationary terminal presence is applied only after route completion. Declared TASK visits must match fixed task coordinates; there is no physical reward-collection radius.

**Collisions are ignored in this version.** Agents may cross or occupy the same position. Obstacles, jerk constraints, and detailed vehicle energy models are outside the initial scope. These motion conventions and the remaining configurable defaults are recorded in the [model contract](../spec/00-model-contract.md).

## Flight-time budget and objectives

Each agent has a flight-time budget measured in seconds. Expenditure is elapsed time from mission start to final arrival, including travel without pauses before arrival. Visits have identical arrival and departure times. Visit velocities are nonzero; a connector may pass through zero velocity between visits.

An agent stops consuming budget after final arrival, remains at the destination, and continues to communicate until the last agent arrives. Thus an early agent's terminal presence affects communication but neither expenditure nor completion time. The mission horizon is the maximum individual completion time.

The ICC stage reports two Pareto objectives:

- Maximize total team reward, counting each task once.
- Minimize average completion time, which is average budget expenditure.
Communication is a constraint. It does not add an objective coordinate.

Path length and mission horizon are diagnostics. Flight-time expenditure is not a physical energy model. Individual budgets remain constraints; a low team average cannot offset an over-budget agent.

## Intermittent communication

Two agents communicate when they have remained continuously within Euclidean range $R$ for a handshake duration $\delta$. After the handshake they exchange data instantly while remaining in range. A genuine interruption resets the handshake. Initial handshakes and synchronization are assumed complete before departure.

Agents store and forward data. Simultaneously linked agents relay instantly through connected components; encounters at different times must form a chronological chain. For example, contact between A and B before B receives C's data does not deliver that data to A.

Define $\Delta$ as the supremum of information staleness over the mission, including limiting peaks immediately before exchanges. A reported $T_c$ slice keeps solutions with $\Delta\le T_c$, equivalent to all-to-all information propagation in every full sliding window of that duration contained in the mission.

For every ordered source–receiver pair, let $P_{nm}$ be its peak information age. The communication violation is $CV=\sum_{n\ne m}\max(0,P_{nm}-T_c)$. Therefore $CV=0$ exactly when $\Delta\le T_c$. `CV` is a constraint and a pool diagnostic, not an objective. A different $T_c$ requires a separate search.

Search diagnostics additionally record the integrated excess age $\sum_{s\ne r}\int_0^T[A_{rs}(t)-T_c]_+\,dt$. It does not alter `CV`, feasibility, or the reported Pareto front. Velocity refinement uses explicit neighborhoods; initialization samples feasible velocity assignments without route-time DP.

No extra final-delivery requirement is imposed. A contact at the destination still needs its handshake unless it is a continuation of an already established link. If the mission is shorter than $T_c$, there is no full sliding window to enforce.

## Free waypoints and solution method

The communication stage adds actual visit positions that are not task locations. They can shape motion and have no intrinsic reward, even when their coordinates coincide with a task. These waypoints are visited positions, not spline control points that the trajectory need not traverse.

MOVNS changes task selection/order/assignment, visit velocities and, in the third stage, free positions. A deterministic connector constructs complete acceleration-feasible trajectories. Continuous contact extraction and temporal propagation then evaluate communication. Minimum-time connectors are a starting point; changed motion states allow communication-aware schedules.

A general nonlinear inner optimizer is optional refinement, not a mandatory part of every candidate evaluation. The baseline uses visit-level motion states and continuous trajectories rather than a uniform time-expanded workspace graph. See [neighborhood structures](neighborhood_structures.md), [variables](variables.md), and [mathematical formulation](math_formulation.md).

## Implementation status

See [implementation milestones](implementation.md) for supported stages, validation, and commands. The step 4 branch now implements continuous communication and free rendezvous waypoints; see the milestone record for supported numerical policies and limits.

Single-agent implementation: MOVNS and the five named KOP neighborhoods are available; see [step 2 status](implementation.md#step-2--single-agent-movns-kop). Team assignment operators are now implemented on the step 3 branch; communication is implemented on the step 4 branch.

Team implementation: individual time budgets, shared reward accounting, and cross-agent assignment moves are available; see [step 3 status](implementation.md#step-3--multi-agent-kop). Collision constraints remain ignored. Communication and FREE visits are always enabled. Contacts arise from trajectories; the solution model has no planned-meeting decisions.

## Step 4 implementation

`team_kop_icc` implements quartic range-contact extraction, maximal-interval handshake handling, initial synchronization, simultaneous connected-component relay, and vector-clock staleness with left limits. An independent reverse temporal-reachability oracle validates propagation. Near-multiple roots that cannot be resolved under the numerical policy are rejected rather than admitted as feasible.

Consecutive fixed route connections determine visit times, with identical arrival and departure times at every visit. Travel is charged until each agent's final arrival. Free positions are bounded by the configured workspace and per-agent visit cap.

The feasible archive `F` contains only movement-, budget-, and communication-feasible solutions and applies epsilon-box Pareto filtering to negative reward and mean completion time. The coverage pool `P` contains valid candidates outside `F`, including infeasible and feasible dominated candidates, and uses fixed objective-space subregions rather than feasibility to preserve coverage. Full propagation is recomputed; pair-contact caching includes the mission horizon.

Current ICC results use schema version 7 and publish only `F`. They include full routes, trajectories, contacts, staleness, two-objective archive snapshots, pool diagnostics, repair outcomes and evaluation-indexed health metrics. Historical schemas retain their original meaning.

The default visit-velocity menu uses eight headings separated by 45 degrees and fractions `0.1, 0.25, 0.5, 0.75, 1` of the directional axis limit (40 nonzero states). Configured fractions must lie in `[0.1, 1]`.
