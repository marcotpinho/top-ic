# Implementation specification: MOVNS → team KOP → intermittent communication

Drafted 2026-10-11. Status: implementation plan; no implementation milestones have been completed by creating this specification.

## Purpose and agreed scope

Build the solution in three scientific stages: (1) MOVNS for the Kinematic Orienteering Problem (KOP), (2) a multi-agent extension with shared rewards, and (3) intermittent communication with free waypoint positions. Supporting engineering work precedes these stages; evaluation and performance work follows them.

Confirmed decisions:

- Flight time is the per-agent budget, replacing distance.
- Expenditure includes all motion and waiting from time zero until an agent's final arrival. Post-arrival presence consumes no budget.
- Agents have acceleration dynamics; collisions are ignored for this version.
- Maximize team reward and minimize average budget expenditure. These are the only Pareto objectives.
- Communication delay Δ is a feasibility metric and search guide, not a third Pareto objective.
- Free waypoints are introduced during the intermittent-communication stage.
- Use MOVNS. KOP's analytical motion-generation ideas are the reference; a full uniform time-expanded workspace graph and a mandatory nonlinear optimization for every candidate are not the baseline architecture.

Implementation defaults that have not been explicitly selected by the user are identified in [model contract](00-model-contract.md). They can be changed without changing the confirmed decisions. This specification describes the target model; the existing `docs/` and implementation still describe parts of the earlier constant-speed TOP-CC/TOP-ICC model. Updating those documents is an implementation milestone, not an assertion that they are already consistent.

## Reading and execution order

| Order | Plan | Deliverable / gate |
|---|---|---|
| 0 | [Model contract](00-model-contract.md) | Unambiguous motion, budget, objectives, and communication semantics |
| 1 | [Foundation and motion](01-foundation-and-motion.md) | Runnable package, typed state representation, validated deterministic connector |
| 2 | [Single-agent MOVNS-KOP](02-single-agent-movns-kop.md) | Two-objective single-agent search and fair KOP-LNS comparison |
| 3 | [Team KOP](03-team-kop.md) | Team task assignment, unique reward accounting, inter-agent moves |
| 4 | [Intermittent communication](04-intermittent-communication.md) | Continuous contacts, propagation, free waypoints, coordinated search |
| 5 | [Validation and release](05-validation-and-release.md) | Reproducible benchmarks, performance measurements, updated interfaces/docs |

Finish each correctness gate before optimizing its performance or moving to the next scientific stage. Stage 3 must retain the ability to run stages 1 and 2 with communication disabled.

## Architectural pipeline

`candidate edit → structural validation → safe lower bounds → deterministic trajectory construction/repair → continuous feasibility and reward evaluation → communication evaluation when enabled → search acceptance → feasible Pareto archive`

Store complete motion choices and derived trajectories. Task order alone is not a full solution. Candidate enumeration may be lazy; evaluation must not silently optimize a stored solution or mutate its motion choices. Optional local optimization is an explicit search move that creates a new candidate.

## References and limits of reuse

[Kinematic Orienteering Problem with Time-Optimal Trajectories for Multirotor UAVs, Meyer and Glock (2022)](https://arxiv.org/abs/2211.16837), especially trajectory generation and the heuristic construction/destruction sections, is the motion and baseline-search reference. Its task-level heading/speed discretization is distinct from a uniformly time-expanded workspace graph. The target extension adds multiple agents, two-objective MOVNS, temporal communication, and movable rendezvous; these are adaptations to implement and validate, not claims inherited from that paper.

Do not claim physical energy minimization: elapsed time is the chosen budget expenditure. Do not claim collision safety, global optimality, continuous-waypoint global search completeness, or exact symbolic contact evaluation. Numerical contact evaluation must have documented error control.
