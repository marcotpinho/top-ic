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
    icc=result.config.mode=="team_kop_icc"
    front=list(result.front)
    # Violation is defined for this run's Tc; other Tc values need independent searches.
    sweep=(result.config.recurrence_bound,) if icc else ()
    slices=[]
    for tc in sweep:
        eligible=[i for i,s in enumerate(front) if s.objectives[2]==0]
        selected=[]
        for i in eligible:
            a=front[i]
            dominated=any(j!=i and all(front[j].objectives[d]<=a.objectives[d] for d in (0,1)) and
                          ((front[j].objectives[0],front[j].objectives[1])!=(a.objectives[0],a.objectives[1])
                           or (front[j].objectives[2],j)<(a.objectives[2],i))
                          for j in eligible)
            if not dominated:selected.append(i)
        chosen=max((front[i] for i in selected),key=lambda s:(s.evaluation.reward,-s.objectives[1]),default=None)
        slices.append({"tc":tc,"front_indices":selected,"front_size":len(selected),
                       "best_reward":chosen.evaluation.reward if chosen else None,
                       "mean_time_at_best_reward":chosen.objectives[1] if chosen else None})
    return {"schema_version":4 if icc else 2,"reward_policy":"explicit_task_visits",
            "objective_policy":"reward_time_violation" if icc else "reward_time",
            "model":"box_double_integrator","connector_version":VERSION,
            "problem":problem_to_dict(result.problem),"config":asdict(result.config),"status":result.status,
            "elapsed_seconds":result.elapsed_seconds,"statistics":result.statistics,
            "front":[solution_to_dict(s) for s in front],"tc_slices":slices,
            "feasible_front_indices":slices[0]["front_indices"] if icc else [],
            "candidate_bank":[solution_to_dict(s) for s in result.candidate_bank],
            "dominated_archive":[solution_to_dict(s) for s in result.dominated_archive]}


def save_result(result,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result_to_dict(result),indent=2,allow_nan=False)+"\n")
