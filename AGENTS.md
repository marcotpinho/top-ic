# Team Orienteering Problem With Intermittent Communication - TOP-ICC

See modeling in `docs/modeling.md`, variable naming in `docs/variables.md` and the mathematical formulation for the problem in `docs/math_formulation.md`.

- Never create new unit tests or try to run existing ones.
- Never update `/docs` unless explicitly told to.
- Specs are saved in `spec/`
- After executing a test, save the results in `results/`
- Each result must also contain a README.md with instructions to reproduce the test.
- Always create each results README from `docs/templates/README.md`, filling in the run-specific details and exact reproduction command.
- Run every new TOP-ICC experiment with `scripts/run_experiment.py`; save its reproduction script, run log, run info, result JSON, neighborhood log, plots, agent-path animation, and template-based README together under `results/`.
- Do not add comments in the code unless it is required to explain obscure logic. In that case, add a brief one-line comment.
- No scope creep: an agent must act solely on what is specified explicitly in a prompt