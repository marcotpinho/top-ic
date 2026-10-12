# Step 3: multi-agent KOP without communication

## Scope

Requires single-agent correctness. Enable multiple agents with common start/end and per-agent flight-time budgets. Keep communication and FREE visits disabled. Collisions are ignored. Every selected task can be reached by several agents, but reward counts once. No forced visit quotas or requirement for every agent to collect reward.

## 3.1 Team representation and evaluation

Extend ordered agent plans, individual trajectories, and evaluation arrays. Sum rewards over the union of task IDs named by explicit TASK visits; do not sum per-route reward totals or incidental crossings. Keep a deterministic first-visitor log for diagnostics, resolving simultaneous arrivals by agent ID, without making that owner determine the objective.

Compute c_m independently, validate every c_m≤B_m, and score `(-team_reward, sum(c_m)/M)`. All agents must reach the destination even if assigned no tasks. Store T=max(c_m) for later communication, but never replace the mean objective by maximum time.

After arrival, position is destination forever within the mission horizon; post-arrival waiting is not a route decision or budget charge. Require zero terminal velocity for this stationary extension under the default endpoint contract.

For identical agents, canonical sorting is optional optimization after correctness; remap visit ownership/references and avoid conflating heterogeneous agents. Routes with equal tasks but different velocities/waits are distinct.

## 3.2 Initialization

Start every agent on a validated direct path. Globally insert tasks by reward/time tradeoff while considering remaining individual budget. Generate alternative assignments using spatial candidate lists, greedy variants, or seeded construction; a cluster partition is a starting heuristic, not a restriction on search.

Create seeds favoring balanced loads and seeds favoring low mean expenditure. Reject an instance with an agent unable to reach the end within its own budget; more budget on another agent cannot compensate.

## 3.3 Team neighborhoods

Retain Step 2 intra-route/state moves and add:

- Transfer one task occurrence between agents, with destination state enumeration and reconnection of both paths.
- Exchange task visits between agents, choosing new boundary velocities as necessary.
- Exchange short subsequences or tails, while preserving terminal states.
- Rebalance an overworked assignment through compound task moves; budget feasibility must be checked for every affected agent.
- Coordinated shaking across a small selected group, reconstructed before archive admission.

Reward-neutral transfer moves can reduce mean completion time or free budget for later insertion. Search needs some exploration outside immediate front improvement, using bounded seed pools/shaking; do not claim every useful route is reachable through only accepted nondominated moves.

Repeated/shared task visits are supported but normally removed when unnecessary in this stage. Duplicate visits may still affect motion continuity; any cleanup must reconstruct and reevaluate rather than assume no effect.

## 3.4 Caching, runner, and outputs

Reuse connector results for unchanged endpoint states. Reconstruct only changed agents initially; concatenate complete trajectories for the team evaluator. Evaluation payload contains per-agent c_m, task set, reward, mean c_m, T, and validity. Return full solutions rather than the current solver's paths-only list, retaining a compatibility adapter if needed.

Log per-agent utilization c_m/B_m; total and mean time; selected/reached task sets; independent reward ownership diagnostics. Plot separate agent trajectories and velocity profiles with actual timing.

## 3.5 Tests and exit gate

- M=1 gives the same trajectory and objectives as the single-agent stage.
- Two agents visiting one task count one reward.
- An empty-task agent still consumes direct-path time.
- Unequal arrival times give mean completion, not T; post-arrival stationary extension changes neither.
- Invalid budget for one agent is not masked by low team average.
- Transfers/exchanges preserve IDs, endpoint state, and task accounting.
- Permuting identical agents leaves physical objectives invariant; heterogeneous permutations are not canonicalized.
- Tiny exhaustive assignment/order/state-menu instances establish the finite-menu team front. Compare search output to it.
- Crossing/co-location fixtures remain feasible, demonstrating collisions are deliberately ignored.

Exit: valid team trajectories, correct global reward and individual budgets, working inter-agent neighborhoods, reproducible tiny-case results. Record this version as the no-communication ablation baseline before proceeding.
