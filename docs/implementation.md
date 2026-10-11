# Implementation milestones

## Step 1 — foundation

Branch: `implementation/step1-foundation`. Implemented versioned JSON instances with explicit seconds budgets, immutable visits and solution decisions, a cached deterministic box-bounded double-integrator connector, continuous task-passage evaluation, and source/installed CLI entry points. Collision constraints are deliberately absent. Team search, MOVNS, communication, and FREE visits are not enabled on this branch.

The connector uses integrated upper/lower Lipschitz velocity envelopes. Their piecewise-quadratic displacement bounds yield candidate common-duration boundaries; convex interpolation constructs a feasible profile on each axis. This differs from reproducing KOP's exact profile-enumeration code and is documented as an independently derived equivalent reachability method for axis-box bounds. Degenerate identical states support zero-duration connections.

Validation: `.venv/bin/python -m pytest -q` passed 8 tests, including 80 random connections, analytic rest-to-rest durations, a sampled-velocity linear-programming reference, wait/budget accounting, incidental reward passage, schema round-trip, and coincident depots. `python main.py` and installed `topcc` both construct the direct smoke trajectory.

Setup: `uv venv --python 3.12 .venv`, then `uv pip install --python .venv/bin/python -e '.[test]'`. Run `topcc --instance instance.json` for a direct-route foundation check. Legacy distance-map files are rejected until explicitly converted to a seconds-budget instance.

Known limits: componentwise bounds only; no magnitude/jerk/collision constraints; numerical residual tolerance is 2e-7; no search in this stage. Existing legacy search modules are replaced in step 2 and are not invoked by this entry point.
