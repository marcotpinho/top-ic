"""Sample cross-agent transfer and exchange; implements N6."""

from collections.abc import Iterator
from dataclasses import replace
from itertools import chain
from random import Random

from ...config import Config, Problem
from ...solution import Solution
from .common import fresh_id, normalize, sample_candidates

name = "assignment"


def _task_positions(solution: Solution) -> Iterator[tuple[int, int]]:
    for agent, route in enumerate(solution.routes):
        for visit_index in range(1, len(route) - 1):
            if route[visit_index].kind == "TASK":
                yield agent, visit_index


def _transfers(solution: Solution) -> Iterator[tuple[str, int, int, int, int]]:
    for agent, visit_index in _task_positions(solution):
        for other_agent, partner_route in enumerate(solution.routes):
            if other_agent == agent:
                continue
            for insertion_index in range(1, len(partner_route)):
                yield "transfer", agent, visit_index, other_agent, insertion_index


def _exchanges(solution: Solution) -> Iterator[tuple[str, int, int, int, int]]:
    positions = tuple(_task_positions(solution))
    for agent, visit_index in positions:
        for other_agent, partner_index in positions:
            if agent < other_agent:
                yield "exchange", agent, visit_index, other_agent, partner_index


def _apply(solution: Solution, proposal: tuple[str, int, int, int, int]) -> Solution:
    kind, agent, visit_index, other_agent, partner_index = proposal
    routes = [list(route) for route in solution.routes]
    if kind == "transfer":
        visit = routes[agent].pop(visit_index)
        moved = replace(
            visit,
            id=fresh_id(solution, "transfer"),
            velocity=(0.0, 0.0),
            wait=0.0,
        )
        routes[other_agent].insert(partner_index, moved)
    else:
        left = routes[agent][visit_index]
        right = routes[other_agent][partner_index]
        routes[agent][visit_index] = replace(right, velocity=(0.0, 0.0), wait=0.0)
        routes[other_agent][partner_index] = replace(
            left, velocity=(0.0, 0.0), wait=0.0
        )
    return normalize(routes, solution.meetings)


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    """Move or exchange TASK visits across agents, preserving reward union (eq. 7)."""
    proposals = chain(_transfers(solution), _exchanges(solution))
    for proposal in sample_candidates(proposals, rng, config.neighborhood_candidates):
        yield _apply(solution, proposal)
