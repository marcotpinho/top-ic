"""Archive selection from explicit nondominated sets and seeded tournaments."""

from hashlib import sha256
from math import inf
from random import Random

from ..solution import Solution


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
    points = [(solution, solution.key, vector(solution)) for solution in source]
    return [
        solution
        for solution, key, point in points
        if not any(
            vector_dominates(other_point, point)
            for _, other_key, other_point in points
            if other_key != key
        )
    ]


def crowding_distances(source: list[Solution], vector=None) -> dict[object, float]:
    """Compute normalized crowding in the supplied objective space."""
    vector = vector or (lambda solution: solution.objectives[:2])
    vectors = {solution.key: vector(solution) for solution in source}
    distances = {solution.key: 0.0 for solution in source}
    if len(source) <= 2:
        return {solution.key: inf for solution in source}
    for axis in range(len(next(iter(vectors.values())))):
        ordered = sorted(
            source,
            key=lambda solution: (vectors[solution.key][axis], repr(solution.key)),
        )
        minimum = vectors[ordered[0].key][axis]
        maximum = vectors[ordered[-1].key][axis]
        if maximum == minimum:
            continue
        distances[ordered[0].key] = inf
        distances[ordered[-1].key] = inf
        for index in range(1, len(ordered) - 1):
            if distances[ordered[index].key] == inf:
                continue
            previous = vectors[ordered[index - 1].key][axis]
            following = vectors[ordered[index + 1].key][axis]
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
    crowding = crowding_distances(source, pool_vector)
    first, second = rng.sample(source, 2)
    if crowding[first.key] == crowding[second.key]:
        return rng.choice((first, second))
    return first if crowding[first.key] > crowding[second.key] else second


def _elite(source: list[Solution]) -> Solution:
    return min(
        source,
        key=lambda solution: (
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
    elite_probability: float = 0.3,
    fixed_pool_probability: float = 0.3,
    elite_enabled: bool = True,
) -> tuple[Solution, dict]:
    """Choose an archive and run its configured two-member tournament."""
    if not (front or pool):
        raise ValueError("Cannot select from empty archives")
    nd_front = nondominated(front, lambda solution: solution.objectives[:2])
    nd_pool = nondominated(pool, pool_vector)
    if policy == "elite_mixture" and front:
        pool_probability = fixed_pool_probability if pool else 0.0
        if not pool_selection_enabled:
            pool_probability = 0.0
        effective_elite_probability = elite_probability if elite_enabled else 0.0
        front_probability = 1.0 - pool_probability - effective_elite_probability
        draw = rng.random()
        elite = _elite(nd_front)
        diverse = [candidate for candidate in nd_front if candidate.key != elite.key]
        if draw < effective_elite_probability:
            source_name = "elite"
            solution = elite
        elif draw < effective_elite_probability + front_probability:
            if diverse:
                source_name = "front"
                solution = _front_tournament(diverse, rng)
            else:
                source_name = "elite"
                solution = elite
        else:
            source_name = "pool"
            solution = _pool_tournament(nd_pool, rng)
    else:
        effective_elite_probability = 0.0
        pool_probability = _selection_probability(
            front,
            pool,
            nd_front,
            nd_pool,
            policy,
        )
        if not pool_selection_enabled and front:
            pool_probability = 0.0
        front_probability = 1.0 - pool_probability
        source_name = "pool" if rng.random() < pool_probability else "front"
        solution = (
            _pool_tournament(nd_pool, rng)
            if source_name == "pool"
            else _front_tournament(nd_front, rng)
        )
    return solution, {
        "source": source_name,
        "rho_elite": effective_elite_probability,
        "rho_front": front_probability,
        "rho_pool": pool_probability,
        "nd_front_size": len(nd_front),
        "nd_pool_size": len(nd_pool),
        "base_cv": solution.evaluation.comm_violation,
        "selection_policy": policy,
        "pool_selection_enabled": pool_selection_enabled,
        "elite_enabled": elite_enabled,
        "base_fingerprint": sha256(repr(solution.key).encode()).hexdigest(),
        "base_reward": solution.evaluation.reward,
        "base_mean_time": solution.objectives[1],
    }
