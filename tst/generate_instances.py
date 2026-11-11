"""Generate all derived JSON instances required by groups C and D."""

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "benchmarks/tsiligirides/icc-20s.json"
DESTINATION = ROOT / "tst/instances"


def write(name, data):
    path = DESTINATION / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def with_agents(base, count, name):
    data = deepcopy(base)
    data["name"] = name
    data["agents"] = [deepcopy(base["agents"][0]) for _ in range(count)]
    return data


def bridge(count):
    agent = {
        "time_budget": 12.0,
        "velocity_axis_limit": [3.0, 3.0],
        "acceleration_axis_limit": [1.5, 1.5],
        "initial_velocity": [0.0, 0.0],
    }
    return {
        "schema_version": 1,
        "budget_unit": "seconds",
        "name": f"bridge{count}",
        "start": [10.0, 0.0],
        "end": [10.0, 0.0],
        "tasks": [
            {"id": "L", "position": [0.0, 0.0], "reward": 50.0},
            {"id": "R", "position": [20.0, 0.0], "reward": 50.0},
        ],
        "agents": [deepcopy(agent) for _ in range(count)],
    }


def generate():
    base = json.loads(SOURCE.read_text())
    paths = [write("icc-20s-2agents.json", with_agents(base, 2, "icc-20s-2agents"))]
    for agents in (1, 3, 5):
        paths.append(
            write(
                f"icc-20s-{agents}agents.json",
                with_agents(base, agents, f"icc-20s-{agents}agents"),
            )
        )
    for budget in (10, 20, 30):
        data = with_agents(base, 2, f"icc-20s-budget{budget}")
        for agent in data["agents"]:
            agent["time_budget"] = float(budget)
        paths.append(write(f"icc-20s-budget{budget}.json", data))
    scaled = with_agents(base, 2, "icc-20s-scaled2")
    scaled["start"] = [2 * value for value in scaled["start"]]
    scaled["end"] = [2 * value for value in scaled["end"]]
    for task in scaled["tasks"]:
        task["position"] = [2 * value for value in task["position"]]
    paths.append(write("icc-20s-scaled2.json", scaled))
    for speed in (1.5, 3.0, 6.0):
        label = str(speed).replace(".", "p")
        data = with_agents(base, 2, f"icc-20s-speed{label}")
        for agent in data["agents"]:
            agent["velocity_axis_limit"] = [speed, speed]
        paths.append(write(f"icc-20s-speed{label}.json", data))
    paths.extend((write("bridge2.json", bridge(2)), write("bridge3.json", bridge(3))))
    return paths


def main():
    for path in generate():
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
