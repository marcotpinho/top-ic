"""Explicit stage gating and portable full-trajectory output."""
from dataclasses import asdict
import json
from pathlib import Path
from .config import Config
from .runner import Runner
from .environment import problem_to_dict
from .operators import SINGLE_NEIGHBORHOODS, TEAM_NEIGHBORHOODS


def run_optimization(problem,config=None):
    config=config or Config()
    if config.mode=="team_kop_icc":
        raise ValueError("Communication and FREE visits are planned for step 4 and are not implemented")
    if config.mode=="single_kop" and problem.num_agents!=1:
        raise ValueError("single_kop requires exactly one agent")
    if config.algorithm=="lns" and problem.num_agents!=1:
        raise ValueError("The matched KOP-LNS baseline currently supports one agent only")
    allowed=TEAM_NEIGHBORHOODS if config.mode=="team_kop" else SINGLE_NEIGHBORHOODS
    unknown=set(config.disabled)-set(allowed)
    if unknown:raise ValueError(f"Unknown disabled neighborhoods: {sorted(unknown)}")
    return Runner(problem,config,allow_team=config.mode=="team_kop").run()


def result_to_dict(result):
    from .trajectory import VERSION
    return {"schema_version":1,"model":"box_double_integrator","connector_version":VERSION,
            "problem":problem_to_dict(result.problem),"config":asdict(result.config),"status":result.status,
            "elapsed_seconds":result.elapsed_seconds,"statistics":result.statistics,
            "front":[{"objectives":s.objectives,"reward":s.evaluation.reward,
                      "completion_times":s.evaluation.completion_times,"reached_tasks":[sorted(x) for x in s.evaluation.reached_tasks],
                      "first_visitors":s.evaluation.first_visitors,"routes":[[asdict(v) for v in r] for r in s.routes],
                      "trajectories":[asdict(t) for t in s.evaluation.trajectories]} for s in result.front]}


def save_result(result,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result_to_dict(result),indent=2,allow_nan=False)+"\n")
