# Plan — periodic mid-line rendezvous on parallel corridors

Goal: on [parallel_corridors](../maps/probes/parallel_corridors/README.md), the best route that meets Tc should have each agent take one corridor, with both agents detouring toward y = 0 at regular intervals to refresh contact.

## What we know

| Run | Best Tc-feasible route at reward 14 | FREE / meetings |
|---|---|---|
| [R = 4 m, Tc = 13 s](../results/step4/parallel_corridors_R4_Tc13_120_20261012/README.md) | mean 18.33 s, Δ 12.70 s, s7 moved to the north agent | none; Tc too loose |
| [R = 8 m, Tc = 7.5 s](../results/step4/parallel_corridors_R8_Tc7.5_120_20261012/README.md) | mean 23.67 s, Δ 6.90 s, cross-corridor task visits | none |

Hand-built routes scored with the solver's velocity refinement ([comparison](../results/step4/parallel_corridors_R8_Tc7.5_120_20261012/reference_routes/compare_comm_ranges.txt)):

| R | No meeting Δ | 1 mid-line pair | 2 mid-line pairs | Solver's cross-corridor route |
|---|---|---|---|---|
| 8 m | 11.77 s | mean 20.23 s, Δ 8.18 s | mean 24.45 s, Δ 6.85 s | mean 23.67 s, Δ 6.90 s |
| 10 m | 10.81 s | mean 19.03 s, Δ 7.11 s | **mean 22.23 s, Δ 5.77 s** | mean 23.67 s, Δ 6.29 s |
| 11 m | 10.13 s | mean 18.27 s, Δ 6.39 s | mean 21.47 s, Δ 5.05 s | mean 23.67 s, Δ 5.46 s |

There are two problems:

1. **The map does not yet reward the behavior.** At R = 8 m the solver's cross-corridor route beats two mid-line meetings. At R = 10 m with Tc = 6.5 s, two meetings are needed and they win by 1.4 s.
2. **The search cannot build the behavior.** In both runs, no FREE visit survived into any saved pool. Reading `src/entities/neighborhoods/meeting.py`, three things work against this map:
   - **Wrong time.** `_meeting_point` uses `communication.bottleneck` time. `sweep` records that at the moment of peak age, which is the *end* of the longest gap, when the agents are already back in contact (here near the shared END). The proposed point lies where the agents meet anyway, not mid-gap.
   - **Wrong slots.** `_free_slots` returns route positions `1..meeting_slot_limit` (default 3), so a pair can only be inserted before each agent's first three visits, whatever their timing.
   - **One stop at a time, always stopped.** `_insert_free_pair` adds one pair plus a `Meeting` link. That forces both endpoints to zero velocity and synchronizes them, the costliest kind of rendezvous. One pair cuts Δ only from 11.8 to about 8 s, which is not enough here, and the archive must keep that intermediate step before a second pair can follow.

## Steps

### 1. Recalibrate the map (small)
- Set `recommended_search` to R = 10 m, Tc = 6.5 s.
- Extend `reference_routes/` to cover crossing once, crossing twice, and k = 1, 2, 3 meeting pairs at R = 10 m. Confirm that two mid-line pairs give the lowest mean time among routes that meet Tc and collect all 14 tasks.
- Run 120 s on the current code as the baseline for steps 2–4.

### 2. Target the middle of the longest gap (`meeting`)
- Compute the gap interval instead of the end of the gap. For the bottleneck pair, take the last effective contact before the bottleneck time, call it t₀, and the bottleneck time t₁. Aim at t* = (t₀ + t₁)/2, and also try (t₀ + t₁)/3 and 2(t₀ + t₁)/3 for longer gaps. The data is already in `communication.contacts[...].effective`.
- Choose the meeting point from both agents' positions at t*: their midpoint, plus points along the segment between them that bring the pair within `fraction · R`. Do not only move toward the host.

### 3. Insert at time-aligned slots (`meeting`)
- Replace `_free_slots` with the index k where `visit_times[k-1] ≤ t* < visit_times[k]` on each agent's route, plus ±1 neighbors. Keep `meeting_slot_limit` as a cap on how many slots are tried, not on which slots.

### 4. Cheaper rendezvous (`meeting`)
- Also propose the FREE pair **without** a `Meeting` link and with zero wait, so velocity refinement can fly through, like the reference routes. Keep the linked, stopped pair as a second proposal.
- Add a "k evenly spaced meetings" proposal. Given the current violation, choose k = ⌈horizon / Tc⌉ − 1 (capped by `max_free_waypoints`) and insert all k pairs at once, at times spread evenly over the mission. This jumps straight to the feasible two-meeting route instead of relying on the archive to keep the one-meeting step.

### 5. Verify
- (Unit tests dropped: `AGENTS.md` now says not to create or run unit tests. Verification is by solver runs only.)
- Runs saved under `results/step4/parallel_corridors_R10_Tc6.5_<seconds>_<date>/`: 120 s and 900 s at seeds 42, 7 and 1, before and after steps 2–4.
- **Success criterion:** the best route that meets Tc and collects all 14 tasks has ≥ 2 FREE pairs with |y| ≤ 5 m, each agent keeps only its own corridor's tasks, and its mean time is ≤ the hand-built reference (22.23 s). Report how many of the three seeds succeed.
- Rerun the [ten-reward relay probe](../results/step4/ten_rewards_relay_probe_300_20261012/README.md) and `free_waypoint_relay` to check that the meeting changes don't regress them.

## Open questions
- Should corridor discipline (no cross-corridor task visits) be a property of the map or a constraint? The model allows any agent to visit any task. If the cross-corridor pattern still wins after step 1, the honest result is that it is the better plan under this model.
- Mid-line contact costs time mainly because the 4 m task spacing lets x-motion finish before the lateral dip. Wider task spacing would make dips cheaper, but it also changes every other route, so it is a later calibration lever.

## Progress (2026-10-12)

- **Map recalibrated twice.** The 7-task, 4 m spacing made each mid-line dip cost about 2.5 s, because the 1.5 m/s² per-axis limit makes lateral motion slower than a short x-leg. Asymmetric crossing then beat meetings (seed 7 baseline: mean 20.83 s). The map now has 5 tasks per corridor, 10 m apart, with R = 10 m and Tc = 7 s; see the [map README](../maps/probes/parallel_corridors/README.md).
- **Search loop scores the shake before generating neighbors.** `meeting` previously always received an unscored shake, so it fell back to route-midpoint, early-slot proposals.
- **Leg-midpoint snapping added** to gap and spread proposals. From the one-corridor split, a single snapped spread reaches 3 mid-line pairs (mean 23.33 s, Δ 6.20 s).
- Runs and diagnostics: [results](../results/step4/parallel_corridors_wide_R10_Tc7_20261012/).
- **Duplicate shakes rescored from the evaluator cache.** A shake that reproduces an archived solution (about 54% for the one-corridor split) returned `None` and fell back to the unscored shake, so the new proposals never ran on the split.
- **Outcome:** 3/3 seeds meet the success criterion at 120 s (mean 22.04, 23.33 and 22.67 s; reference 23.48 s), versus 0/3 at baseline. The 900 s seed-42 run also succeeds (mean 22.04 s, 3 FREE pairs). The regression probes keep full reward and their FREE relays; see [regression](../results/step4/regression_meeting_changes_20261012/README.md).
- **Unit tests dropped:** `AGENTS.md` now says not to create or run them.
