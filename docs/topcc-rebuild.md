# TOP-CC-shaped rebuild

The code immediately before this rebuild is frozen at the annotated tag
`pre-topcc-rebuild-20261012` (commit `71d738c`). The structural reference is
[TOP-CC `src` at `38c863a`](https://github.com/marcotpinho/top-cc/tree/38c863a99b3211c1fe09423c1d6082190868311e/src).
The new `src/entities` package follows its Runner, Archive, Neighborhood,
Solution, and Evaluator responsibilities. It keeps this project's continuous
kinematic and communication model and its occurrence-level visit representation.

## Evaluation boundary

`src/evaluation_core` carries the frozen motion, scheduling, contact, propagation,
and evaluator algorithms, with the unused modes removed. The five fixed cases in
`tests/data/evaluator_reference.json` hold the complete input decisions and
output records: trajectories, contacts, peak staleness Δ, bottleneck, and
objectives. The three ICC cases are checked for exact equality after JSON
normalization. The two older-mode cases remain in the immutable historical
record and can be checked against the frozen tag.

## Search boundary

The new Runner owns one `random.Random(config.seed)` and passes it to the
Archive and Neighborhood. The evaluator uses no randomness. Each neighborhood
samples from its candidate set; the Runner gives each family an independent
ruin-and-recreate perturbation of the same selected seed. Initialization
includes direct, geometric partition, random partition, and synchronized
cooperative seeds. The ICC epsilon archive retains a distinct exact-zero
violation box, and a bounded pool keeps physically feasible rejected
candidates for search. The old LNS runner is available at the frozen tag.

The new operator generators in `src/entities/neighborhoods/` are written from
the model contract and named neighborhood descriptions in
`docs/neighborhood_structures.md`. They do not call the historical generators.
The registry in `src/entities/neighborhood.py` defines the enabled ICC list.
The unused historical neighborhood tree, including `wait`, `free_move`,
`free_remove`, `duplicate_rendezvous`, `velocity`, and `velocity_dp`, was
removed from the working tree. It remains at the frozen tag.
The continuous evaluator remains the final authority for motion, budgets,
contact, and recurrence validity.

## Validation

Run `.venv/bin/python -m pytest -q`. The small relay gate exhausts all 25
two-agent task-order pairs over two tasks, including omitted tasks and
duplicate visits. Its best feasible rewards are 7, 7, and 12 for
`T_c = 0.5, 2, 10` seconds. The new search matches these values with seeds
1, 2, and 3. This is an exhaustive reference for the stated finite task-only
space, not for arbitrary free-waypoint positions or velocities. A separate
large-`T_c` gate checks the team-KOP objectives and best reward, and a repeated
seed checks front reproducibility. The active solver accepts only
`team_kop_icc`; the team-KOP side of the large-`T_c` comparison uses an
independent task-reward and connector-time scorer over the finite relay space.
