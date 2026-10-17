# `{MAP_NAME}` — `{RUN_LABEL}`

## Map parameters and constraints

- **Instance:** [`{INSTANCE_PATH}`]({INSTANCE_LINK}); SHA-256: `{INSTANCE_SHA256}`.
- **Map scale and frame:** `{UNITS}`, `{MAP_BOUNDS_OR_SIZE}`.
- **Agents:** `{AGENT_COUNT}`; starts: `{START_POSITIONS}`; destinations: `{END_POSITIONS}`; initial velocities: `{INITIAL_VELOCITIES}`.
- **Motion limits:** per-axis velocity `{VELOCITY_LIMITS}`; per-axis acceleration `{ACCELERATION_LIMITS}`.
- **Flight-time budgets:** `{BUDGETS_SECONDS}`.
- **Tasks and rewards:** `{TASK_COUNT}` tasks; total available reward `{TOTAL_REWARD}`; reward collection rule `{REWARD_RULE}`.
- **Communication constraints:** range R = `{COMMUNICATION_RANGE}` `{DISTANCE_UNITS}`; handshake delta = `{HANDSHAKE_TIME}` s; recurrence bound Tc = `{RECURRENCE_BOUND}` s.
- **Other model constraints and assumptions:** `{COLLISION_RULES}`, `{WAIT_RULES}`, `{OTHER_ASSUMPTIONS}`.
- **Search:** algorithm `{ALGORITHM}`; seed `{SEED}`; time cap `{TIME_CAP_SECONDS}` s; evaluation cap `{EVALUATION_CAP}`; outer-iteration cap `{ITERATION_CAP}`.
- **Neighborhood repetition:** normalized hypervolume threshold tau = `{HV_THRESHOLD}`; maximum passes p_max = `{MAX_NEIGHBORHOOD_PASSES}`.
- **Archive:** epsilon widths `{EPSILON_WIDTHS}`; normalized hypervolume reference point `{HV_REFERENCE_POINT}`; normalization scales `{HV_SCALES}`.
- **Other search limits:** `{WAYPOINT_STEPS}`, `{WAIT_STEPS}`, `{MAX_FREE_WAYPOINTS}`, `{NEIGHBORHOOD_CANDIDATES}`, `{DISABLED_NEIGHBORHOODS}`.

## Results and observations

- **Status and elapsed time:** `{STATUS}`; `{ELAPSED_SECONDS}` s of `{TIME_CAP_SECONDS}` s.
- **Search work:** `{EVALUATION_COUNT}` evaluations, `{OUTER_ITERATION_COUNT}` outer iterations, and `{NEIGHBORHOOD_PASS_COUNTS}` neighborhood passes.
- **Final archive:** `{ARCHIVE_SIZE}` solutions; `{TC_FEASIBLE_ARCHIVE_SIZE}` satisfy Tc.
- **Best Tc-feasible solution:** reward `{BEST_FEASIBLE_REWARD}` of `{TOTAL_REWARD}`; mean completion time `{BEST_FEASIBLE_MEAN_TIME}` s; peak staleness Delta = `{BEST_FEASIBLE_DELTA}` s.
- **Archive hypervolume:** `{FINAL_HYPERVOLUME}` using reference `{HV_REFERENCE_POINT}` and scales `{HV_SCALES}`.
- **Observed result:** `{CONCISE_EVIDENCE_BASED_OBSERVATIONS}`.
- **Limitations:** `{RELEVANT_LIMITATIONS_OR_NONE}`.
- **Artifacts:** result JSON [`{RESULT_JSON}`]({RESULT_JSON_LINK}); best path [`{BEST_PATH_PLOT}`]({BEST_PATH_LINK}); Pareto frontier [`{PARETO_PLOT}`]({PARETO_LINK}); Delta tradeoff [`{DELTA_PLOT}`]({DELTA_LINK}); Pareto evolution [`{PARETO_EVOLUTION_PLOT}`]({PARETO_EVOLUTION_LINK}). Remove links for plots not generated and add links for other artifacts.
- **Neighborhood execution log:** [`{NEIGHBORHOOD_LOG}`]({NEIGHBORHOOD_LOG_LINK}), listing each generated neighborhood call in execution order, including phase, iteration/pass where applicable, candidate counts, and generation time.

## Reproduce

- **Repository revision:** commit `{GIT_COMMIT}`; local changes or patches: `{PATCH_OR_NONE}`.
- **Environment:** Python `{PYTHON_VERSION}`; dependencies `{DEPENDENCY_SOURCE_OR_LOCKFILE}`; operating system `{OPERATING_SYSTEM}`.
- **Reproduction script:** [`{REPRODUCE_SCRIPT}`]({REPRODUCE_SCRIPT_LINK}). Run from the repository root:

  ```sh
  {REPRODUCE_COMMAND}
  ```

- **Plot generation command:**

  ```sh
  {PLOT_COMMAND}
  ```

- **Validation performed:** `{VALIDATION_COMMAND_AND_OUTCOME_OR_NOT_RUN}`.
- **Reproduction note:** `{DETERMINISM_AND_RUNTIME_VARIABILITY_NOTE}`.
