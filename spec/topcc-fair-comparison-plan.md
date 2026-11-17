# Matched TOP-CC-C0 versus TOP-ICC comparison

## Goal

Compare saved solution quality under constant communication without saturating the routing budgets or penalizing TOP-CC for lacking a feasible initializer.

## Instances and common controls

- Original maps: post-disaster, wildfire, pipeline, and agriculture.
- Same task coordinates, rewards, starts, destinations, agent count, communication range, seed 42, and 600-second wall-clock budget.
- One numerical-library thread per process; paired concurrent execution under `caffeinate -i`.
- Unique team reward is the primary quality measure. Mean completion time breaks reward ties within each method.

## TOP-ICC

- Current acceleration-bounded KOP connector.
- Exact `Tc=0`, requiring the instantaneous range graph to remain connected.
- Native temporal budgets from the original maps.
- Execution through `scripts/run_experiment.py` with batch evaluation and one million evaluation/iteration caps.

## TOP-CC-C0

- Isolated clone at `../top-cc-comparison-20261116`, revision `38c863a` plus the comparison adapter.
- Original piecewise-linear constant-speed motion at 3 m/s.
- Each temporal budget `B` becomes distance budget `3B`.
- `multi_vis` variant so agents may share visits, matching the possibility of shared visits in TOP-ICC.
- A deterministic reward-per-insertion convoy seed gives all agents one identical budget-valid route, guaranteeing an initially connected solution. The original TOP-CC MOVNS then runs without changes to its operators or dominance relation.
- Saved solutions are post-validated by exact continuous range-graph connectivity and distance budgets.

## Reporting

- Best connected reward and its mean completion time for each method and map.
- Best budget-valid TOP-CC reward without connectivity as a diagnostic only.
- Evaluation counts and feasibility counts.
- No cross-model claim based on completion time because the motion models differ.
- One-seed results are observed outcomes, not statistical estimates.

## Outputs

- Run bundles: `results/2026-11-16/topcc-fair-comparison/<map>/<method>/`.
- Parsed CSV and analysis Markdown in the campaign root.
- Updated comparison table and protocol discussion in `paper/experiments.tex`.
