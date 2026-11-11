"""Padded tensor representations of route decisions and trajectories."""

from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from ..config import Problem
from ..evaluation_core.trajectory import AgentTrajectory, State, connect
from ..solution import Solution, Visit

KIND_TO_CODE = {"START": 1, "TASK": 2, "FREE": 3, "END": 4}
CODE_TO_KIND = {value: key for key, value in KIND_TO_CODE.items()}


@dataclass(frozen=True)
class RouteBatch:
    kind: np.ndarray
    task: np.ndarray
    pos: np.ndarray
    vel: np.ndarray
    nvis: np.ndarray
    task_ids: tuple[str, ...]

    @property
    def size(self) -> int:
        return int(self.kind.shape[0])


@dataclass(frozen=True)
class TrajectoryBatch:
    dur: np.ndarray
    pc_n: np.ndarray
    p_pos: np.ndarray
    p_vel: np.ndarray
    p_acc: np.ndarray
    p_len: np.ndarray
    p_t0: np.ndarray
    comp: np.ndarray
    trajectories: tuple[tuple[AgentTrajectory, ...], ...]
    visit_times: tuple[tuple[tuple, ...], ...]

    @property
    def size(self) -> int:
        return int(self.comp.shape[0])


def select_trajectories(batch: TrajectoryBatch, indices: list[int]) -> TrajectoryBatch:
    selected = np.asarray(indices, dtype=np.int64)
    return TrajectoryBatch(
        batch.dur[selected],
        batch.pc_n[selected],
        batch.p_pos[selected],
        batch.p_vel[selected],
        batch.p_acc[selected],
        batch.p_len[selected],
        batch.p_t0[selected],
        batch.comp[selected],
        tuple(batch.trajectories[index] for index in indices),
        tuple(batch.visit_times[index] for index in indices),
    )


def routes_to_tensor(solutions: list[Solution], problem: Problem) -> RouteBatch:
    if not solutions:
        raise ValueError("A route batch cannot be empty")
    agents = problem.num_agents
    if any(len(solution.routes) != agents for solution in solutions):
        raise ValueError("Every solution must match the problem agent count")
    visits = max(len(route) for solution in solutions for route in solution.routes)
    shape = (len(solutions), agents, visits)
    kind = np.zeros(shape, dtype=np.int8)
    task = np.full(shape, -1, dtype=np.int16)
    pos = np.zeros((*shape, 2), dtype=np.float64)
    vel = np.zeros((*shape, 2), dtype=np.float64)
    nvis = np.zeros(shape[:2], dtype=np.int16)
    task_ids = tuple(item.id for item in problem.tasks)
    task_index = {task_id: index for index, task_id in enumerate(task_ids)}
    for batch_index, solution in enumerate(solutions):
        for agent, route in enumerate(solution.routes):
            nvis[batch_index, agent] = len(route)
            for visit_index, visit in enumerate(route):
                kind[batch_index, agent, visit_index] = KIND_TO_CODE[visit.kind]
                pos[batch_index, agent, visit_index] = visit.position
                vel[batch_index, agent, visit_index] = visit.velocity
                if visit.kind == "TASK":
                    task[batch_index, agent, visit_index] = task_index[visit.task_id]
    return RouteBatch(kind, task, pos, vel, nvis, task_ids)


def tensor_to_solutions(batch: RouteBatch) -> list[Solution]:
    solutions = []
    for batch_index in range(batch.size):
        routes = []
        for agent in range(batch.kind.shape[1]):
            route = []
            for visit_index in range(int(batch.nvis[batch_index, agent])):
                code = int(batch.kind[batch_index, agent, visit_index])
                visit_kind = CODE_TO_KIND[code]
                task_index = int(batch.task[batch_index, agent, visit_index])
                task_id = batch.task_ids[task_index] if task_index >= 0 else None
                route.append(
                    Visit(
                        f"batch:{batch_index}:{agent}:{visit_index}",
                        visit_kind,
                        tuple(batch.pos[batch_index, agent, visit_index]),
                        tuple(batch.vel[batch_index, agent, visit_index]),
                        task_id=task_id,
                    )
                )
            routes.append(tuple(route))
        solutions.append(Solution(tuple(routes)))
    return solutions


def _route_trajectory(
    route: tuple[Visit, ...], limits
) -> tuple[AgentTrajectory, tuple, list]:
    pieces = []
    connections = []
    times = []
    elapsed = 0.0
    for start, end in pairwise(route):
        times.append((elapsed, elapsed))
        connection = connect(
            State(start.position, start.velocity),
            State(end.position, end.velocity),
            limits,
        )
        connections.append(connection)
        for piece in connection.pieces:
            pieces.append(
                type(piece)(
                    piece.position,
                    piece.velocity,
                    piece.acceleration,
                    piece.duration,
                    piece.start_time + elapsed,
                )
            )
        elapsed += connection.duration
    times.append((elapsed, elapsed))
    trajectory = AgentTrajectory(
        tuple(pieces),
        elapsed,
        State(route[0].position, route[0].velocity),
        State(route[-1].position, route[-1].velocity),
    )
    return trajectory, tuple(times), connections


def solutions_to_trajectories(
    solutions: list[Solution], problem: Problem
) -> TrajectoryBatch:
    if not solutions:
        raise ValueError("A trajectory batch cannot be empty")
    built = []
    max_connections = 1
    max_pieces = 1
    for solution in solutions:
        rows = []
        for agent, route in enumerate(solution.routes):
            trajectory, times, connections = _route_trajectory(
                route, problem.limits[agent]
            )
            rows.append((trajectory, times, connections))
            max_connections = max(max_connections, len(connections))
            max_pieces = max(
                max_pieces,
                max((len(connection.pieces) for connection in connections), default=0),
            )
        built.append(rows)
    batch_size = len(solutions)
    agents = problem.num_agents
    base = (batch_size, agents, max_connections)
    piece_shape = (*base, max_pieces)
    dur = np.zeros(base, dtype=np.float64)
    pc_n = np.zeros(base, dtype=np.int16)
    p_pos = np.zeros((*piece_shape, 2), dtype=np.float64)
    p_vel = np.zeros((*piece_shape, 2), dtype=np.float64)
    p_acc = np.zeros((*piece_shape, 2), dtype=np.float64)
    p_len = np.zeros(piece_shape, dtype=np.float64)
    p_t0 = np.zeros(piece_shape, dtype=np.float64)
    comp = np.zeros((batch_size, agents), dtype=np.float64)
    trajectory_rows = []
    visit_time_rows = []
    for batch_index, rows in enumerate(built):
        trajectories = []
        visit_times = []
        elapsed = np.zeros(agents, dtype=np.float64)
        for agent, (trajectory, times, connections) in enumerate(rows):
            trajectories.append(trajectory)
            visit_times.append(times)
            comp[batch_index, agent] = trajectory.completion_time
            for connection_index, connection in enumerate(connections):
                dur[batch_index, agent, connection_index] = connection.duration
                pc_n[batch_index, agent, connection_index] = len(connection.pieces)
                for piece_index, piece in enumerate(connection.pieces):
                    index = (batch_index, agent, connection_index, piece_index)
                    p_pos[index] = piece.position
                    p_vel[index] = piece.velocity
                    p_acc[index] = piece.acceleration
                    p_len[index] = piece.duration
                    p_t0[index] = elapsed[agent] + piece.start_time
                elapsed[agent] += connection.duration
        trajectory_rows.append(tuple(trajectories))
        visit_time_rows.append(tuple(visit_times))
    return TrajectoryBatch(
        dur,
        pc_n,
        p_pos,
        p_vel,
        p_acc,
        p_len,
        p_t0,
        comp,
        tuple(trajectory_rows),
        tuple(visit_time_rows),
    )
