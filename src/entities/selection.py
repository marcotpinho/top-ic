"""Archive selection from explicit nondominated sets and seeded tournaments."""

from collections.abc import Callable
from math import inf
from random import Random

from ..solution import Solution

Dominance = Callable[[Solution, Solution], bool]


def communication_feasible(solution: Solution) -> bool:
    return solution.evaluation.comm_violation <= 1e-13


def constrained_dominates(first: Solution, second: Solution) -> bool:
    """Compare expansion outcomes by feasibility, CV, and reported objectives."""
    first_feasible = communication_feasible(first)
    second_feasible = communication_feasible(second)
    if first_feasible != second_feasible:
        return first_feasible
    if not first_feasible:
        return first.evaluation.comm_violation < second.evaluation.comm_violation
    return first.dominates(second)


def legacy_pool_dominates(first: Solution, second: Solution) -> bool:
    """Reproduce the superseded lexicographic pool rule for ablation."""
    first_cv = first.evaluation.comm_violation
    second_cv = second.evaluation.comm_violation
    if first_cv != second_cv:
        return first_cv < second_cv
    return first.dominates(second)


def pool_vector(solution: Solution) -> tuple[float, float, float]:
    """Return the three minimized coordinates used to construct ND_P."""
    return (
        solution.evaluation.comm_violation,
        -solution.evaluation.reward,
        solution.objectives[1],
    )


def vector_dominates(first: tuple, second: tuple) -> bool:
    return all(a <= b for a, b in zip(first, second)) and any(
        a < b for a, b in zip(first, second)
    )


def nondominated(source: list[Solution], vector) -> list[Solution]:
    """Return members not dominated by another member of the same archive."""
    vectors = {solution.key: vector(solution) for solution in source}
    return [
        solution
        for solution in source
        if not any(
            vector_dominates(vectors[other.key], vectors[solution.key])
            for other in source
            if other.key != solution.key
        )
    ]


def nondominated_by_relation(
    source: list[Solution], dominates: Dominance
) -> list[Solution]:
    """Return the nondominated set for the legacy pairwise relation."""
    return [
        solution
        for solution in source
        if not any(
            dominates(other, solution) for other in source if other.key != solution.key
        )
    ]


def crowding_distances(source: list[Solution]) -> dict[object, float]:
    """Compute NSGA-II crowding in the two reported objectives of ND_F."""
    distances = {solution.key: 0.0 for solution in source}
    if len(source) <= 2:
        return {solution.key: inf for solution in source}
    for axis in range(2):
        ordered = sorted(
            source,
            key=lambda solution: (solution.objectives[axis], repr(solution.key)),
        )
        distances[ordered[0].key] = inf
        distances[ordered[-1].key] = inf
        minimum = ordered[0].objectives[axis]
        maximum = ordered[-1].objectives[axis]
        if maximum == minimum:
            continue
        for index in range(1, len(ordered) - 1):
            if distances[ordered[index].key] == inf:
                continue
            previous = ordered[index - 1].objectives[axis]
            following = ordered[index + 1].objectives[axis]
            distances[ordered[index].key] += (following - previous) / (
                maximum - minimum
            )
    return distances


def _stable_key(solution: Solution) -> tuple:
    return (
        solution.evaluation.comm_violation,
        -solution.evaluation.reward,
        solution.objectives[1],
        repr(solution.key),
    )


def _legacy_tournament(
    source: list[Solution], dominates: Dominance, rng: Random
) -> Solution:
    if len(source) == 1:
        return source[0]
    first, second = rng.sample(source, 2)
    if dominates(first, second):
        return first
    if dominates(second, first):
        return second
    return min(first, second, key=_stable_key)


def _front_tournament(source: list[Solution], rng: Random) -> Solution:
    if len(source) == 1:
        return source[0]
    crowding = crowding_distances(source)
    first, second = rng.sample(source, 2)
    first_distance = crowding[first.key]
    second_distance = crowding[second.key]
    if first_distance != second_distance:
        return first if first_distance > second_distance else second
    return min(first, second, key=_stable_key)


def _pool_tournament(source: list[Solution], rng: Random) -> Solution:
    if len(source) == 1:
        return source[0]
    first, second = rng.sample(source, 2)
    return min(
        (first, second),
        key=lambda solution: (
            solution.evaluation.comm_violation,
            -solution.evaluation.reward,
            solution.objectives[1],
            repr(solution.key),
        ),
    )


def _selection_probability(
    front: list[Solution],
    pool: list[Solution],
    nd_front: list[Solution],
    nd_pool: list[Solution],
    policy: str,
) -> float:
    if not pool:
        return 0.0
    if not front:
        return 1.0
    if policy == "legacy_fraction":
        front_fraction = len(nd_front) / len(front)
        pool_fraction = len(nd_pool) / len(pool)
        denominator = front_fraction + pool_fraction
        return pool_fraction / denominator if denominator else 0.5
    return len(nd_pool) / (len(nd_front) + len(nd_pool))


def select_base(
    front: list[Solution],
    pool: list[Solution],
    rng: Random,
    policy: str = "nd_count",
    pool_selection_enabled: bool = True,
) -> tuple[Solution, dict]:
    """Choose an archive and run its configured two-member tournament."""
    if not (front or pool):
        raise ValueError("Cannot select from empty archives")
    nd_front = nondominated(front, lambda solution: solution.objectives[:2])
    nd_pool = (
        nondominated_by_relation(pool, legacy_pool_dominates)
        if policy == "legacy_fraction"
        else nondominated(pool, pool_vector)
    )
    pool_probability = _selection_probability(
        front,
        pool,
        nd_front,
        nd_pool,
        policy,
    )
    if not pool_selection_enabled and front:
        pool_probability = 0.0
    source_name = "pool" if rng.random() < pool_probability else "front"
    if source_name == "pool":
        source = pool if policy == "legacy_fraction" else nd_pool
        dominates = legacy_pool_dominates
    else:
        source = front if policy == "legacy_fraction" else nd_front
        dominates = Solution.dominates
    if policy == "legacy_fraction":
        solution = _legacy_tournament(source, dominates, rng)
    elif source_name == "pool":
        solution = _pool_tournament(source, rng)
    else:
        solution = _front_tournament(source, rng)
    return solution, {
        "source": source_name,
        "rho_front": 1.0 - pool_probability,
        "rho_pool": pool_probability,
        "nd_front_size": len(nd_front),
        "nd_pool_size": len(nd_pool),
        "base_cv": solution.evaluation.comm_violation,
        "selection_policy": policy,
        "pool_selection_enabled": pool_selection_enabled,
    }
