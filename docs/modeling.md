# Team KOP with Intermittent Communication — Modeling

This document describes the target research model. The implementation is being planned in [spec/](../spec/README.md); the foundation implements acceleration-aware trajectories; search stages are tracked in [implementation status](implementation.md).

## Research stages

1. Apply Multi-Objective Variable Neighborhood Search (MOVNS) to single-agent Kinematic Orienteering (KOP).
2. Extend the problem to multiple agents with shared reward accounting.
3. Add intermittent communication and freely positioned waypoints for rendezvous and motion shaping.

[KOP](https://arxiv.org/abs/2211.16837) supplies the motion-generation reference. The team, communication, and multiobjective extensions are part of this project. Free waypoints are enabled only in the third stage.

## Tasks, agents, and motion

Tasks are fixed 2D locations with nonnegative rewards. Each agent chooses which tasks to reach and in which order, starting at a common start and ending at a common destination. A task's reward is collected once for the team, by its first physical visitor. Other agents may visit it, and an agent may return to a task location for communication. Task passage does not require stopping; incidental passage also collects reward.

Agents follow double-integrator dynamics: position changes with velocity, and velocity changes with bounded acceleration. Their velocities remain continuous; acceleration may change between motion pieces. A visit includes position and velocity, so task order alone does not specify a complete solution.

The proposed initial motion convention is KOP-compatible componentwise velocity and acceleration bounds. These are axis bounds, not bounds on Euclidean speed or acceleration magnitude. Initial velocity is configurable, with zero as the default. Final velocity is zero so that agents can remain stationary after arrival. Numerical task-passage tolerance is distinct from a physical reward-collection radius.

**Collisions are ignored in this version.** Agents may cross or occupy the same position. Obstacles, jerk constraints, and detailed vehicle energy models are outside the initial scope. These motion conventions and the remaining configurable defaults are recorded in the [model contract](../spec/00-model-contract.md).

## Flight-time budget and objectives

Each agent has a flight-time budget measured in seconds. Expenditure is elapsed time from mission start to final arrival, including travel and all waiting before arrival. Waiting is possible only at zero velocity; stopping requires feasible deceleration.

An agent stops consuming budget after final arrival, remains at the destination, and continues to communicate until the last agent arrives. Thus an early agent's terminal waiting affects communication but neither expenditure nor completion time. The mission horizon is the maximum individual completion time.

There are exactly two Pareto objectives:

- Maximize total team reward, counting each task once.
- Minimize average completion time, which is average budget expenditure.

Path length and mission horizon are diagnostics. Flight-time expenditure is not a physical energy model. Individual budgets remain constraints; a low team average cannot offset an over-budget agent.

## Intermittent communication

Two agents communicate when they have remained continuously within Euclidean range $R$ for a handshake duration $\delta$. After the handshake they exchange data instantly while remaining in range. A genuine interruption resets the handshake. Initial handshakes and synchronization are assumed complete before departure.

Agents store and forward data. Simultaneously linked agents relay instantly through connected components; encounters at different times must form a chronological chain. For example, A meeting B before B receives C's data does not deliver that data to A.

The requirement is all-to-all information propagation in every full sliding window of duration $T_c$ contained in the mission. Define $\Delta$ as the supremum of information staleness over the mission, including limiting peaks immediately before exchanges. Feasibility requires $\Delta\le T_c$.

$\Delta$ is a constraint metric and search guide, not a third Pareto objective. Communication-infeasible but otherwise valid candidates can be explored in a separate bounded working pool. Smaller violation guides them toward feasibility; lower $\Delta$ can break objective ties or prioritize exploration among feasible solutions.

No extra final-delivery requirement is imposed. A contact at the destination still needs its handshake unless it is a continuation of an already established link. If the mission is shorter than $T_c$, there is no full sliding window to enforce.

## Free waypoints and solution method

The communication stage adds actual visit positions that are not task locations. They can create meetings or shape motion and have no intrinsic reward. An incidental task crossing still counts. These waypoints are visited positions, not spline control points that the trajectory need not traverse.

MOVNS changes task selection/order/assignment, visit velocities, stopped waits, and, in the third stage, free positions and coordinated meetings. A deterministic connector constructs complete acceleration-feasible trajectories. Continuous contact extraction and temporal propagation then evaluate communication. Minimum-time connectors are a starting point; waiting and changed motion states allow communication-aware schedules.

A general nonlinear inner optimizer is optional refinement, not a mandatory part of every candidate evaluation. The baseline uses visit-level motion states and continuous trajectories rather than a uniform time-expanded workspace graph. See [neighborhood structures](neighborhood_structures.md), [variables](variables.md), and [mathematical formulation](math_formulation.md).

## Implementation status

See [implementation milestones](implementation.md) for supported stages, validation, and commands. Communication and free-waypoint sections describe the later target extension, not completed functionality.
