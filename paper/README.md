# TOP-ICC manuscript

`root.tex` is the entry point. The formulation follows `../docs/math_formulation.md` and the implemented `team_kop_icc` solver. `experiments.tex` reports the four saved triple-flight-budget scenario runs in `../results/step4/scenarios_search_guidance_triple_budget_20261012_4maps/`, plus the separate two-agent relay probe in `../results/step4/free_waypoint_relay_120_20261012/`.

Build from this folder with a standard LaTeX installation:

```sh
pdflatex root.tex
bibtex root
pdflatex root.tex
pdflatex root.tex
```

The figures use relative paths into `results/`, so keep the repository layout when compiling. The four-map table describes one seed per map under a 115-second search allowance. The budget-only reward column is the best **saved** motion- and flight-budget-valid candidate, not an optimum. The original-budget comparison mentioned in the text comes from the archived `flight-budget-comparison.json`; its full prior run folder is not present in the current workspace. No matched TOP-CC baseline or multi-seed statistical study is claimed.
