"""Tensor construction of communication invitation grids."""

import numpy as np

from .neighborhoods import _candidate_batch, _dedupe, _insert, _workspace
from .tensors import tensor_to_solutions


def invitation_candidates(solution, ranked_pairs, problem, config):
    pairs = list(ranked_pairs)
    if not pairs:
        return []
    host_points = np.asarray(
        [
            solution.routes[host][host_index].position
            for _, _, host, host_index, _, _ in pairs
        ]
    )
    guest_points = np.asarray(
        [
            solution.routes[guest][guest_index].position
            for _, _, _, _, guest, guest_index in pairs
        ]
    )
    angles = np.arctan2(
        guest_points[:, 1] - host_points[:, 1],
        guest_points[:, 0] - host_points[:, 0],
    )
    offsets = np.asarray((-0.25, 0.0, 0.25))
    grid_angles = (angles[:, None] + offsets[None, :]).reshape(-1)
    repeated_hosts = np.repeat(host_points, len(offsets), axis=0)
    radius = 0.9 * config.comm_range
    points = repeated_hosts + radius * np.column_stack(
        (np.cos(grid_angles), np.sin(grid_angles))
    )
    repeated_pairs = [pair for pair in pairs for _ in offsets]
    proposals = [
        (guest, max(1, guest_index), point)
        for pair, point, valid in zip(
            repeated_pairs, points, _workspace(points, config.waypoint_workspace)
        )
        for _, _, _, _, guest, guest_index in (pair,)
        if valid
    ]
    if not proposals:
        return []
    batch = _candidate_batch(solution, problem, len(proposals), True)
    for row, (guest, insertion, point) in enumerate(proposals):
        _insert(
            batch,
            row,
            guest,
            insertion,
            3,
            -1,
            point,
            batch.vel[row, guest, insertion - 1].copy(),
        )
    return _dedupe(tensor_to_solutions(batch))
