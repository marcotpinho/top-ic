# ICC architecture

The executable solver supports `team_kop_icc` with MOVNS. The pre-rebuild
implementation is frozen at `pre-topcc-rebuild-20261012`.

## Module map

| Module | Responsibility |
|---|---|
| `src/main.py`, `src/solver.py` | Parse an ICC run, construct its workspace, and serialize the result. |
| `src/config.py`, `src/solution.py` | Immutable physical inputs, search settings, visit occurrences, routes, and meetings. |
| `src/entities/runner.py` | Own the run's single seeded random generator and coordinate search. |
| `src/entities/seed_construction.py`, `selection.py`, `shaking.py`, `search_loop.py` | Build initial solutions, select a base, perturb it, and run sampled families. |
| `src/entities/neighborhood.py`, `src/entities/neighborhoods/` | Register the eight ICC families and generate candidates with an explicit RNG. |
| `src/entities/archive.py`, `pool.py`, `archive_updates.py` | Maintain the ε-box front, exact-zero violation layer, and dominated working pool. |
| `src/evaluation_core/` | Validate structure, schedule meetings, construct continuous trajectories, credit rewards, check budgets, evaluate communication, and assemble objectives. |
| `src/entities/statistics.py` | Package counters, history, and the final run result. |

The historical families `wait`, `free_move`, `free_remove`,
`duplicate_rendezvous`, `velocity`, and `velocity_dp` are available at the
`pre-topcc-rebuild-20261012` tag. The working tree keeps only the active ICC
registry.

## One iteration

The Runner selects a solution from the ε front or dominated pool. For each
enabled family it independently ruins and recreates that same base, then
samples at most `neighborhood_candidates` proposals. The same RNG flows
through selection, shaking, and generation. Each proposal receives velocity
refinement and the full evaluation pipeline. Physically valid solutions enter
the ε archive or the dominated pool. The search loop records evaluation and
front changes before moving to the next family or iteration.

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
| $V_c$ | `Evaluation.comm_violation`, the third minimization objective |

The full evaluator output for three ICC fixtures is compared exactly with
the frozen record in `tests/data/evaluator_reference.json`. The same file
retains two historical-mode records from before the ICC-only cleanup.
