"""Execute batch-evaluator checks F1-F6."""

import argparse
import json
import random
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import numpy as np
from common import CheckLog, close, records
from topcc.core.evaluation.batch.communication import batch_sweep
from topcc.core.evaluation.batch.contacts import _polynomial_intervals, _quartics
from topcc.core.evaluation.batch.tensors import routes_to_tensor
from topcc.core.evaluation.communication import sweep
from topcc.core.evaluation.contacts import range_intervals
from topcc.core.evaluation.equivalence import equivalent
from topcc.core.problem.config import velocity_menu
from topcc.core.problem.environment import problem_from_dict, smoke_problem
from topcc.core.routing.solution import direct_solution
from topcc.entities.evaluation.BatchEvaluator import BatchEvaluator
from topcc.entities.evaluation.ContactBatch import ContactBatch
from topcc.entities.evaluation.ContactRecord import ContactRecord
from topcc.entities.evaluation.ContactUncertain import ContactUncertain
from topcc.entities.evaluation.Evaluator import Evaluator
from topcc.entities.evaluation.TrajectoryBatch import TrajectoryBatch
from topcc.entities.evaluation.batch._Segment import _Segment
from topcc.entities.problem.Config import Config
from topcc.entities.routing.Solution import Solution
from topcc.entities.routing.Visit import Visit
from verify_propagation import CASES

ROOT = Path(__file__).resolve().parents[1]


def deserialize_solution(row):
    return Solution(
        tuple(
            tuple(
                Visit(
                    visit["id"],
                    visit["kind"],
                    visit["position"],
                    visit["velocity"],
                    visit.get("task_id"),
                )
                for visit in route
            )
            for route in row["routes"]
        )
    )


def perturb(solution, problem, config, rng, index):
    routes = [list(route) for route in solution.routes]
    agent = rng.randrange(len(routes))
    route = routes[agent]
    mode = rng.randrange(4)
    if mode == 0 and len(route) > 2:
        visit_index = rng.randrange(1, len(route) - 1)
        menu = velocity_menu(problem.limits[agent], config)
        velocity = rng.choice(menu)
        visit = route[visit_index]
        route[visit_index] = Visit(
            f"f1-velocity-{index}",
            visit.kind,
            visit.position,
            velocity,
            visit.task_id,
        )
    elif mode == 1 and len(route) > 3:
        left, right = rng.sample(range(1, len(route) - 1), 2)
        route[left], route[right] = route[right], route[left]
    elif mode == 2 and len(route) > 2:
        route.pop(rng.randrange(1, len(route) - 1))
    else:
        insertion = rng.randrange(1, len(route))
        before, after = route[insertion - 1], route[insertion]
        fraction = rng.random()
        position = tuple(
            before.position[axis]
            + fraction * (after.position[axis] - before.position[axis])
            + rng.uniform(-0.25, 0.25)
            for axis in range(2)
        )
        route.insert(
            insertion,
            Visit(
                f"f1-free-{index}",
                "FREE",
                position,
                before.velocity,
            ),
        )
    return Solution(tuple(tuple(route) for route in routes))


def equivalent_contract(batch, scalar):
    if (
        batch.valid != scalar.valid
        or batch.validation_status != scalar.validation_status
    ):
        return False
    if not batch.valid:
        return True
    if batch.objectives != scalar.objectives:
        return False
    if not close(batch.comm_violation, scalar.comm_violation, 1e-9):
        return False
    batch_peaks = batch.communication.pair_peaks if batch.communication else ()
    scalar_peaks = scalar.communication.pair_peaks if scalar.communication else ()
    return close(batch_peaks, scalar_peaks, 1e-9)


def contact_batch(agents, links):
    pairs = tuple(
        (first, second)
        for first in range(agents)
        for second in range(first + 1, agents)
    )
    rows = [tuple(links.get(pair, ())) for pair in pairs]
    capacity = max(1, max((len(row) for row in rows), default=0))
    intervals = np.full((1, len(pairs), capacity, 2), np.nan)
    counts = np.zeros((1, len(pairs)), dtype=np.int16)
    contact_records = []
    for pair_index, (pair, row) in enumerate(zip(pairs, rows)):
        counts[0, pair_index] = len(row)
        if row:
            intervals[0, pair_index, : len(row)] = row
        contact_records.append(ContactRecord(pair, row, row))
    return ContactBatch(
        intervals, counts, np.zeros(1, dtype=np.int8), pairs, (tuple(contact_records),)
    )


def dummy_trajectories(agents):
    zeros3 = np.zeros((1, agents, 1))
    zeros4 = np.zeros((1, agents, 1, 1))
    zeros5 = np.zeros((1, agents, 1, 1, 2))
    return TrajectoryBatch(
        zeros3,
        zeros3.astype(np.int16),
        zeros5,
        zeros5.copy(),
        zeros5.copy(),
        zeros4,
        zeros4.copy(),
        np.full((1, agents), 10.0),
        ((),),
        ((),),
    )


def polynomial_cases(log):
    cases = (
        ("A4", (-5, -2), (1, 0), (0, 0), 10, 2),
        ("A5a", (-5, -(2 + 1e-10)), (1, 0), (0, 0), 10, 2),
        ("A5b", (-5, -(2 - 1e-10)), (1, 0), (0, 0), 10, 2),
        ("A5c", (-5, -(2 + 1e-6)), (1, 0), (0, 0), 10, 2),
        ("A5d", (-5, -(2 - 1e-6)), (1, 0), (0, 0), 10, 2),
    )
    for name, position, velocity, acceleration, duration, radius in cases:
        segment = _Segment(0, 0, 0.0, duration, position, velocity, acceleration)
        coefficients, q, scales = _quartics([segment], radius)
        try:
            scalar = range_intervals(position, velocity, acceleration, duration, radius)
        except ContactUncertain:
            scalar = "unresolved"
        try:
            batch = _polynomial_intervals(
                coefficients[0], q[0], duration, radius, scales[0]
            )
        except ContactUncertain:
            batch = "unresolved"
        log.check(
            f"F2 {name}",
            scalar == batch or (scalar != "unresolved" and close(scalar, batch, 1e-9)),
            {"scalar": scalar, "batch": batch},
        )


def padding_and_size(log):
    problem = smoke_problem(2)
    config = Config(batch_eval=True, max_seconds=30)
    short = direct_solution(problem)
    routes = [list(route) for route in short.routes]
    routes[0].insert(
        1,
        Visit(
            "padding-task",
            "TASK",
            problem.tasks[0].position,
            routes[0][0].velocity,
            problem.tasks[0].id,
        ),
    )
    long = Solution(tuple(tuple(route) for route in routes))
    separate = [
        BatchEvaluator(problem, config).evaluate(item).evaluation
        for item in (short, long)
    ]
    together = BatchEvaluator(problem, config).evaluate_batch([short, long])
    log.check(
        "F3 padding independence",
        all(
            equivalent(left, right.evaluation)
            for left, right in zip(separate, together)
        ),
    )
    tensor = routes_to_tensor([short, long], problem)
    log.check(
        "F3 route lengths",
        tuple(map(tuple, tensor.nvis)) == ((2, 2), (3, 2)),
        tensor.nvis.tolist(),
    )
    single = BatchEvaluator(problem, config).evaluate(short).evaluation
    thousand = BatchEvaluator(problem, config).evaluate_batch([short] * 1000)
    log.check(
        "F4 batch 1 vs 1000",
        all(equivalent(single, item.evaluation) for item in thousand),
        len(thousand),
    )


def sweep_cases(log):
    for name, (agents, links, _, _) in CASES.items():
        scalar = sweep(agents, 10.0, records(links), 5.0)
        batch = batch_sweep(
            dummy_trajectories(agents), contact_batch(agents, links), 5.0
        ).results[0]
        log.check(
            f"F5 {name}",
            close(batch.pair_peaks, scalar.pair_peaks, 1e-9),
            {"scalar": scalar.pair_peaks, "batch": batch.pair_peaks},
        )


def f1(log, source_result, count, seed, chunk_size):
    data = json.loads(source_result.read_text())
    problem = problem_from_dict(data["problem"])
    config = Config(**data["config"])
    scalar = Evaluator(
        problem, replace(config, batch_eval=False, batch_neighborhoods=False)
    )
    batch = BatchEvaluator(
        problem, replace(config, batch_eval=True, batch_neighborhoods=True)
    )
    rng = random.Random(seed)
    bases = [deserialize_solution(row) for row in data["front"]]
    solutions = []
    seen = set()
    attempts = 0
    scalar_seconds = 0.0
    while len(solutions) < count and attempts < count * 200:
        candidate = perturb(rng.choice(bases), problem, config, rng, attempts)
        attempts += 1
        if candidate.key in seen:
            continue
        started = perf_counter()
        scored = scalar.evaluate(candidate)
        scalar_seconds += perf_counter() - started
        if scored.evaluation.valid:
            seen.add(candidate.key)
            solutions.append(candidate)
    log.check(
        "F1 generated valid solutions",
        len(solutions) == count,
        {"requested": count, "generated": len(solutions), "attempts": attempts},
    )
    divergences = []
    batch_seconds = 0.0
    for start in range(0, len(solutions), chunk_size):
        chunk = solutions[start : start + chunk_size]
        started = perf_counter()
        evaluated = batch.evaluate_batch(chunk)
        batch_seconds += perf_counter() - started
        for offset, (solution, scored) in enumerate(zip(chunk, evaluated)):
            reference = scalar.evaluate(solution).evaluation
            if not equivalent_contract(scored.evaluation, reference):
                divergences.append(start + offset)
    log.check("F1 scalar-batch contract", not divergences, divergences[:20])
    log.check(
        "F6 timing reported",
        scalar_seconds > 0 and batch_seconds > 0,
        {
            "scalar_seconds": scalar_seconds,
            "batch_seconds": batch_seconds,
            "speedup": scalar_seconds / batch_seconds if batch_seconds else None,
        },
    )


def latest_result():
    candidates = sorted(
        ROOT.glob("results/**/result.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return next(
        (path for path in candidates if json.loads(path.read_text()).get("front")), None
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-result")
    parser.add_argument("--count", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--chunk-size", type=int, default=1000)
    args = parser.parse_args()
    source = (
        (ROOT / args.source_result).resolve() if args.source_result else latest_result()
    )
    if source is None:
        raise SystemExit("F1 requires a saved result.json with a nonempty front")
    log = CheckLog("F-batch")
    polynomial_cases(log)
    padding_and_size(log)
    sweep_cases(log)
    f1(log, source, args.count, args.seed, args.chunk_size)
    report = log.report()
    report["source_result"] = str(source.relative_to(ROOT))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
