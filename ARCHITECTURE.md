# ICC architecture

The executable solver supports `team_kop_icc` with MOVNS. The pre-rebuild
implementation is frozen at `pre-topcc-rebuild-20261012`.

## Module map

| Module | Responsibility |
|---|---|
| `src/main.py`, `src/solver.py` | Parse an ICC run, construct its workspace, and serialize the result. |
| `src/config.py`, `src/solution.py` | Immutable physical inputs, search settings, visit occurrences, and routes. |
| `src/velocity_initialization.py` | Sample seeded-random menu velocities with a feasible continuation across every route connector. |
| `src/entities/runner.py` | Own the run's single seeded random generator and coordinate search. |
| `src/entities/seed_construction.py`, `selection.py`, `shaking.py`, `search_loop.py` | Build initial solutions, select a base, perturb it, and run sampled families. |
| `src/entities/neighborhood.py`, `src/entities/neighborhoods/` | Register the eleven ICC families and generate candidates with an explicit RNG. |
| `src/entities/archive.py`, `pool.py`, `archive_updates.py` | Maintain the ε-box front, exact-zero violation layer, and dominated working pool. |
| `src/evaluation_core/` | Validate structure, schedule routes, construct continuous trajectories, credit rewards, check budgets, evaluate communication, and assemble objectives. |
| `src/entities/budget_repair.py` | Repair over-budget candidates by dropping TASK visits at lowest team reward loss per exact route-time saved. |
| `src/entities/statistics.py` | Package counters, history, and the final run result. |

The historical families `wait`, `free_move`, `free_remove`,
`duplicate_rendezvous`, `velocity`, and `velocity_dp` are available at the
`pre-topcc-rebuild-20261012` tag. The working tree keeps only the active ICC
registry.

## One iteration

The Runner selects a solution from feasible archive `F` or coverage pool `P`.
`ND_F` is Pareto in reward/time and `ND_P` is Pareto in CV/reward/time.
Archive probabilities use their nondominated-set cardinalities; tournaments use
only those sets, with crowding in `F` and CV then reward in `P`. It then applies one
10–40% ruin-and-recreate move, evaluates it, and runs up to three communication
repair rounds when `CV` is positive. Every enabled VND family then generates at
most `neighborhood_candidates` proposals from that working solution. The same
RNG flows through selection, shaking, repair, and generation. Every distinct
proposal receives the full evaluation pipeline. Communication-feasible
nondominated solutions update `F`; every other valid candidate updates `P`.
After a family pass, the runner measures the normalized two-objective hypervolume
of `F`. If its gain exceeds
`neighborhood_hv_tau`, the family runs another pass from a seeded-random choice
among the solutions newly retained in the front, up to
`neighborhood_max_passes`. The default threshold is 0 and the default pass cap
is 3. Hypervolume uses minimization objectives normalized by total task reward
and the maximum agent time budget, with reference point `(1, 1)`. The search
loop records evaluation and front changes before moving to the next family or
iteration.

Run JSON stores `statistics.profiling` in wall-clock seconds. Its
`search_loop_seconds` covers the complete local-search loop after seed
construction. `evaluation_seconds` covers all candidate processing and archive updates. `evaluator_seconds` is the time inside
the evaluation core. Each enabled neighborhood records call count and total,
shake, generation, and evaluation durations. `shake_seconds` covers only the
perturbation; evaluating the shaken solution belongs to `evaluation_seconds`.
These phases are included in `total_seconds`. Top-level `elapsed_seconds` covers the full run, including
seed construction and result packaging.

## Formulation map

The notation follows [docs/variables.md](docs/variables.md) and
[docs/math_formulation.md](docs/math_formulation.md).

| Symbol | Code |
|---|---|
| $\pi_m$, $\kappa_{mk}$, $\iota_{mk}$ | `Solution.routes[m]`, `Visit.kind`, `Visit.task_id` |
| $z_{mk}$, $v_{mk}$, $w_{mk}$ | `Visit.position`, `Visit.velocity`, `Visit.wait` |
| $\mathcal P$ | `Solution.meetings` |
| $p_m(t)$, $v_m(t)$, $a_m(t)$ | `AgentTrajectory`, `MotionPiece` |
| $c_m$, $B_m$ | `Evaluation.completion_times[m]`, `Problem.time_budgets[m]` |
| $Q$, $\bar c$ | `Evaluation.reward`, `Evaluation.objectives[1]` |
| $R$, $\delta$, $T_c$ | `Config.comm_range`, `handshake_time`, `recurrence_bound` |
| $\mathcal C_{mn}$, $\mathcal I_{mn}$ | `ContactRecord.raw`, `ContactRecord.effective` |
| $h_{nm}(\sigma)$, $\Delta$ | `CommunicationResult.final_clock`, `peak_staleness` |
| $CV$ | `Evaluation.comm_violation`, sum of ordered-pair staleness excesses |
| $F$ | `entities.archive.Archive.front`, feasible reward–time archive |
| $P$ | `entities.pool.CoveragePool`, valid candidates outside $F$ |

The full evaluator output for three ICC fixtures is compared exactly with
the frozen record in `tests/data/evaluator_reference.json`. The same file
retains two historical-mode records from before the ICC-only cleanup.
