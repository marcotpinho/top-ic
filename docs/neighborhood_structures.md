# Neighborhood structures

The ICC search uses these operators, in the registry order:

- **remove** — Remove one explicit TASK visit from an agent route.
- **replace** — Replace one TASK visit with an unreached task.
- **assignment** — Transfer a TASK visit between agents or exchange TASK visits across two agents.
- **reorder** — Relocate, swap, or reverse interior visits within one agent route.
- **insert** — Insert one unreached TASK visit at a position in an agent route.
- **relay** — Replace one shared TASK visit with a nearby FREE visit while another agent retains the task.
- **free_near_visit** — Add a FREE visit within communication range of a randomly sampled visit on another agent's route, when both adjacent motion connectors are feasible.
- **free_segment** — Insert or relocate one FREE visit by sampling the actual connector between its neighbors and a perpendicular offset in `[-r,+r]`; r defaults to R, TASK assignments stay fixed, and both edited connectors must be feasible (N19).
- **unlink** — Remove a FREE visit.
- **velocity_change** — Change one interior visit velocity to another menu value when both adjacent connectors remain feasible.
- **velocity_segment** — Change menu velocities over configured contiguous blocks of interior visits (default lengths 2 and 3), keeping affected connectors feasible.

## Search perturbations

Before each neighborhood family runs, the search perturbs the selected base with one seeded ruin-and-recreate move. Strength starts at 1 and increases by 1 every four outer iterations:

- **Route removal** — Choose a route containing TASK visits and remove all its TASK visits, keeping its START, END, and FREE visits.
- **Contiguous sequence removal** — Choose a TASK visit and remove up to strength + 1 consecutive interior visits, including TASK or FREE visits, from that route.
- **Spatially related removal** — Choose a TASK visit as an anchor and remove up to strength + 1 TASK visits nearest to it by Euclidean distance across the team.
- **Noisy greedy recreation** — Reinsert removed visits in random order, sampling up to `recreate_sample_slots` route slots and choosing the lowest detour cost plus seeded random noise.

The perturbation preserves route endpoints, assigns fresh occurrence IDs, and assigns recreated visits the receiving agent's nonzero initial velocity with immediate departure. Each neighborhood family starts from its own perturbed copy of the selected base.

## Budget repair

When a generated candidate exceeds an agent's flight-time budget, `budget_repair_drop` previews removing each TASK visit on an overloaded route using exact scheduled trajectory durations. It repeatedly drops the occurrence with the lowest team reward loss per second saved until all routes meet their budgets or no feasible task deletion can restore them. Duplicate TASK visits can be removed with zero team reward loss while another route still serves that task. The repair leaves FREE visits untouched, then sends a repaired candidate through the normal communication evaluator.
