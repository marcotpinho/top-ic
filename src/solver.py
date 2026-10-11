"""Explicit stage gating and portable full-trajectory output."""
from dataclasses import asdict
import json
from pathlib import Path
from .config import Config
from .runner import Runner
from .environment import problem_to_dict
from .operators import SINGLE_NEIGHBORHOODS, TEAM_NEIGHBORHOODS, ICC_NEIGHBORHOODS


def run_optimization(problem,config=None):
    config=config or Config()
    if config.mode=="team_kop_icc":
        if config.algorithm!="movns":raise ValueError("ICC mode uses MOVNS")
        if config.waypoint_workspace is None:
            from dataclasses import replace
            points=[problem.start,problem.end,*[t.position for t in problem.tasks]]
            margin=max(config.comm_range,max(config.waypoint_steps,default=1.))
            config=replace(config,waypoint_workspace=(min(p[0] for p in points)-margin,max(p[0] for p in points)+margin,
                                                       min(p[1] for p in points)-margin,max(p[1] for p in points)+margin))
    if config.mode=="single_kop" and problem.num_agents!=1:
        raise ValueError("single_kop requires exactly one agent")
    if config.algorithm=="lns" and problem.num_agents!=1:
        raise ValueError("The matched KOP-LNS baseline currently supports one agent only")
    allowed=ICC_NEIGHBORHOODS if config.mode=="team_kop_icc" else TEAM_NEIGHBORHOODS if config.mode=="team_kop" else SINGLE_NEIGHBORHOODS
    unknown=set(config.disabled)-set(allowed)
    if unknown:raise ValueError(f"Unknown disabled neighborhoods: {sorted(unknown)}")
    return Runner(problem,config,allow_team=config.mode in ("team_kop","team_kop_icc")).run()


def solution_to_dict(s):
    return {"objectives":s.objectives,"reward":s.evaluation.reward,"feasible":s.evaluation.valid,
            "motion_budget_valid":s.evaluation.motion_budget_valid,"validation_status":s.evaluation.validation_status,
            "reason":s.evaluation.reason,"peak_staleness":s.evaluation.peak_staleness,"comm_violation":s.evaluation.comm_violation,
            "completion_times":s.evaluation.completion_times,"visit_times":s.evaluation.visit_times,
            "reached_tasks":[sorted(x) for x in s.evaluation.reached_tasks],"first_visitors":s.evaluation.first_visitors,
            "routes":[[asdict(v) for v in r] for r in s.routes],"meetings":[asdict(p) for p in s.meetings],
            "trajectories":[asdict(t) for t in s.evaluation.trajectories],
            "communication":asdict(s.evaluation.communication) if s.evaluation.communication else None}


def result_to_dict(result):
    from .trajectory import VERSION
    return {"schema_version":2,"model":"box_double_integrator","connector_version":VERSION,
            "problem":problem_to_dict(result.problem),"config":asdict(result.config),"status":result.status,
            "elapsed_seconds":result.elapsed_seconds,"statistics":result.statistics,
            "front":[solution_to_dict(s) for s in result.front],
            "candidate_bank":[solution_to_dict(s) for s in result.candidate_bank],
            "working_pool":[solution_to_dict(s) for s in result.working_pool]}


def save_result(result,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result_to_dict(result),indent=2,allow_nan=False)+"\n")
