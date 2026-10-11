"""Versioned instances: budgets must explicitly be seconds."""
import json
from dataclasses import asdict
from pathlib import Path
from .config import Problem, Task, MotionLimits


def problem_from_dict(data):
    if data.get("schema_version") != 1 or data.get("budget_unit") != "seconds":
        raise ValueError("Expected schema_version=1 and budget_unit='seconds'; convert legacy distance instances explicitly")
    agents = data["agents"]
    return Problem(tuple(Task(str(t["id"]), t["position"], float(t["reward"])) for t in data["tasks"]),
                   data["start"], data["end"], tuple(a["time_budget"] for a in agents),
                   tuple(MotionLimits(a.get("velocity_axis_limit", (3,3)), a.get("acceleration_axis_limit", (1.5,1.5))) for a in agents),
                   tuple(a.get("initial_velocity", (0,0)) for a in agents), data.get("name", "instance"))


def problem_to_dict(problem):
    return {"schema_version": 1, "budget_unit": "seconds", "name": problem.name,
            "start": problem.start, "end": problem.end, "tasks": [asdict(t) for t in problem.tasks],
            "agents": [{"time_budget": b, "velocity_axis_limit": l.velocity, "acceleration_axis_limit": l.acceleration,
                        "initial_velocity": v} for b,l,v in zip(problem.time_budgets,problem.limits,problem.initial_velocities)]}


def load_problem_instance(path):
    if Path(path).suffix != ".json":
        raise ValueError("Legacy text maps require explicit conversion to a seconds-budget JSON instance")
    return problem_from_dict(json.loads(Path(path).read_text()))


def save_problem_instance(problem, path):
    Path(path).write_text(json.dumps(problem_to_dict(problem), indent=2)+"\n")


def smoke_problem(agents=1):
    return Problem((Task("a", (2.,2.), 5.),Task("b", (4.,-1.), 8.),Task("c", (6.,2.), 3.)),
                   (0.,0.), (8.,0.), (14.,)*agents, (MotionLimits(),)*agents, ((0.,0.),)*agents, "smoke")
