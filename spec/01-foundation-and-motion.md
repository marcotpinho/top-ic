# Step 1: engineering foundation and deterministic motion generation

## Entry and repository findings

The inspected code is a legacy TOP-CC implementation, not an acceleration-aware KOP implementation:

| Current component | Finding | Planned action |
|---|---|---|
| `src/config.py` | Budgets and constant speeds; TOP-CC labels | Add explicit time budget and motion-bound fields; version instance schema |
| `src/solution.py` | Signed M×(N−2) matrix encoding selection/order; cannot represent repeat/free visits or velocities/waits | Replace with ordered visit occurrences and stored motion choices |
| `src/solution.py` | Equal scores count as dominance; all coordinates maximized | Strict two-objective minimization dominance; separate deduplication |
| `src/evaluator.py` | Scores reward, sampled RSSI, negative maximum distance | New completion-time evaluator and later continuous contact evaluator |
| `src/archive.py` | RSSI-based selection and arbitrary score dimensions | Two-dimensional feasible front plus separate working pool |
| `src/runner.py` | Materializes neighbors; initializes through random paths | Lazy candidate pipeline, explicit seed archive, bounded shaking/VND |
| `src/numba_kernels.py` | Constant-speed and signed-matrix assumptions | Reuse only independent verified utilities; port after reference code passes |
| `src/environment.py` | Legacy task/depot reorder and untyped budget | Stable IDs, explicit depot metadata, versioned loading/conversion |
| Entry points / packaging | `main.py` imports removed `CONFIG`/`src.movns`; `src/*` imports `topcc`; package mapping needs verification | Establish one runnable entry point and explicit setuptools layout |
| Documentation | Distance budget, constant speed, RSSI/Δ objectives; neighborhood document uses earliest STN scheduling | Migrate after model contract lands; rederive locality claims |

Existing modifications/deletions belong to the workspace. Do not reset or restore them as part of implementation. No dedicated tests were found by the repository file search; establish meaningful motion/evaluator/search tests.

## 1.1 Runnable package and migration boundary

- Verify the current Python environment and install/import path. Keep `topcc` as a compatibility package name initially if practical, with an explicit mapping to `src`; avoid a broad rename mixed into algorithm changes.
- Route the root script through the supported CLI instead of removed APIs. Add a tiny in-memory smoke instance independent of absent map files.
- Create modes `single_kop`, `team_kop`, and `team_kop_icc`; do not derive model semantics from an operator name such as `unique_vis`.
- Legacy files require explicit budget units/conversion. Never silently interpret an old distance budget as seconds. Retain a converter or report an actionable validation error.
- Add config validation: finite nonnegative rewards; positive budgets and motion limits; valid endpoint IDs; consistent per-agent arrays; communication fields required only in ICC mode.

Gate: package import and CLI smoke run work; invalid inputs fail before search; one modern instance round-trips without losing units or IDs.

## 1.2 Data and evaluation contracts

Implement proposed types in `src/config.py`, `src/solution.py`, and new `src/trajectory.py`:

- `Visit`: occurrence ID, kind, optional task ID, position, velocity state, wait.
- `MotionPiece`: local start state p0,v0, constant a, duration; absolute time offset derived when assembling an agent trajectory.
- `AgentTrajectory`: ordered pieces, actual final arrival, `position(t)`/`velocity(t)`, terminal stationary extension via mission evaluator.
- `Solution`: agent plans, optional planned-meeting references, trajectory construction version, immutable evaluation payload or invalidated cache.
- `Evaluation`: reward set/value, completion times, objective pair, budget excesses, motion validity, optional Δ/violation, numerical status, diagnostics.

Separate source decisions from derived caches. Copies must not share mutable visit/trajectory arrays. A hash must include every non-derived motion/timing/free-position decision and problem/connector configuration. Keep stable IDs distinct from mutable route indices. Hashes may bucket floats for deduplication, but cache reuse requires exact canonical values or a checked equivalence; do not evaluate one geometry using another geometry's cached contacts.

## 1.3 KOP motion connector

Implement a deterministic `connect(start_state, end_state, limits)` returning constant-acceleration pieces and duration, or structured failure. Read and derive the KOP trajectory-generation equations before coding; use complete synchronization-pattern feasibility checks rather than assuming the maximum of the two independent axis-optimal durations is always feasible.

Procedure:

1. Solve 1D bounded-velocity/bounded-acceleration profiles for each axis, including nonzero endpoint velocities, both displacement signs, triangular/trapezoidal cases, and zero displacement.
2. Enumerate relevant classical and synchronization profiles with deterministic ordering.
3. Determine the earliest common feasible duration across axes, reconstruct each axis at that duration, and verify all phase durations and speed bounds.
4. Merge the union of x/y phase-change times into 2D constant-acceleration pieces.
5. Independently integrate pieces and verify endpoint position/velocity, nonnegative duration, bounds, continuity, and reported total time.

Do not claim global optimality for a simplified connector until its pattern coverage is validated. Numeric failures are not proof that states are unreachable. Expose error categories and keep a trusted slow reference implementation.

For a constant-acceleration piece at local τ: `p(τ)=p0+v0τ+aτ²/2`, `v(τ)=v0+aτ`. Under componentwise limits, check velocity extrema at endpoints and constant acceleration directly. Zero-duration pieces are removed canonically; a stationary dwell is a=v=0.

Gate: deterministic repeated output; correct integration; 1D analytic cases; diagonal/reversed/nonzero-velocity cases; axis-synchronization regression; degenerate identical states. Compare selected outputs to an independent fine-resolution optimal-control reference with convergence checks, not only samples of the implementation's own equations.

## 1.4 Scheduling and caching

Initially assemble consecutive minimum-time connections plus explicit zero-velocity waits. Cache connectors by both endpoint positions/velocities, bounds, numerical policy, and connector version. Free positions later invalidate corresponding keys; avoid precomputing all possible state pairs.

For the later communication stage, add an explicit fixed-duration connector only if needed. Longer requested duration is not automatically feasible with prescribed nonzero endpoint velocities; naive time scaling changes endpoint velocities. Initial timing flexibility comes from valid stopped waits and altered boundary velocity choices.

Allow local reconstruction of segments adjacent to edited visits when unaffected boundary states remain fixed. Shift downstream absolute times as required. Neither unchanged geometry nor local connection costs imply communication locality.

## 1.5 Documentation migration

Update `docs/modeling.md`, `docs/variables.md`, `docs/math_formulation.md`, and `docs/neighborhood_structures.md` to the contract. Remove obsolete MILP-only notation; express constraints over visit occurrences and trajectories. Replace length objectives/budgets and three-dimensional archive definitions. State ignored collisions and numerical validity. Replace constant-speed contact quadratics by quartic range polynomials. Audit existing STN/triangle-inequality/locality and neighborhood-disjointness claims; retain only those valid under fixed kinematic connectors and their stated assumptions.

Deliverable: foundation commit(s), motion reference implementation, unit fixtures, runnable smoke command, migrated model documentation. No communication/free-waypoint search yet.
