"""Animate saved continuous trajectories and effective communication links."""

from pathlib import Path

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.lines import Line2D

from .viz_paths import AGENT_COLORMAPS, draw_task_markers, sample_trajectory


def _positions_at_times(trajectory: dict, times: np.ndarray) -> np.ndarray:
    """Evaluate saved quadratic pieces exactly; hold position after arrival."""
    positions = np.tile(trajectory["end"]["position"], (len(times), 1)).astype(float)
    positions[times <= 0] = trajectory["start"]["position"]
    for piece in trajectory["pieces"]:
        local = times - piece["start_time"]
        active = (local >= 0) & (local <= piece["duration"])
        elapsed = local[active, None]
        positions[active] = (
            np.asarray(piece["position"])
            + elapsed * np.asarray(piece["velocity"])
            + 0.5 * elapsed**2 * np.asarray(piece["acceleration"])
        )
    return positions


def _create_scene(problem: dict, solution: dict) -> tuple:
    """Draw fixed map context and allocate one moving marker per agent."""
    figure, axis = plt.subplots(figsize=(8, 6))
    reached = set().union(*(set(ids) for ids in solution.get("reached_tasks", [])))
    draw_task_markers(axis, problem["tasks"], reached)
    samples = [sample_trajectory(route) for route in solution["trajectories"]]
    trails = []
    markers = []
    for agent, (positions, _, _) in enumerate(samples):
        color = plt.get_cmap(AGENT_COLORMAPS[agent % len(AGENT_COLORMAPS)])(0.75)
        axis.plot(*positions.T, color=color, alpha=0.18)
        trails.append(axis.plot([], [], color=color, linewidth=2)[0])
        markers.append(
            axis.plot([], [], "o", color=color, markersize=8, label=f"Agent {agent + 1}")[0]
        )
    axis.scatter(*problem["start"], marker="s", color="black", label="Start")
    axis.scatter(*problem["end"], marker="X", color="black", label="End")
    axis.set(xlabel="x (m)", ylabel="y (m)", title="Agent paths and communication")
    axis.set_aspect("equal", adjustable="datalim")
    axis.margins(0.08)
    axis.grid(alpha=0.2)
    return figure, axis, samples, trails, markers


def _create_links(axis, solution: dict) -> list[tuple[dict, Line2D]]:
    """Allocate links; visibility follows the evaluator's effective intervals."""
    contacts = (solution.get("communication") or {}).get("contacts", [])
    links = []
    for index, contact in enumerate(contacts):
        line = axis.plot(
            [], [], color="tab:green", linestyle=":", linewidth=2,
            label="Effective communication" if index == 0 else None,
        )[0]
        links.append((contact, line))
    return links


def _update_links(links: list, positions: np.ndarray, time: float) -> None:
    """Connect simultaneous agent positions while effective contact is active."""
    for contact, line in links:
        active = any(start <= time <= end for start, end in contact["effective"])
        line.set_visible(active)
        if active:
            line.set_data(positions[contact["agents"]].T)


def save_path_animation(
    problem: dict,
    solution: dict,
    output_path: str | Path,
    fps: int = 15,
    playback_seconds: float = 12.0,
) -> Path:
    """Save a GIF of the plotted solution, with a shared mission clock for all agents.

    Saved motion pieces determine positions; arrival holds the agent at its end.
    Links become active immediately within communication range.
    Rendering consumes no search randomness and runs after optimization finishes.
    """
    if fps <= 0 or playback_seconds <= 0:
        raise ValueError("Animation fps and playback duration must be positive")
    horizon = max(route["completion_time"] for route in solution["trajectories"])
    times = np.linspace(0.0, horizon, max(2, round(fps * playback_seconds) + 1))
    positions = np.stack([
        _positions_at_times(route, times) for route in solution["trajectories"]
    ], axis=1)
    figure, axis, samples, trails, markers = _create_scene(problem, solution)
    links = _create_links(axis, solution)
    clock = axis.text(0.02, 0.98, "", transform=axis.transAxes, va="top")
    axis.legend(loc="lower right", fontsize=8)
    figure.tight_layout()

    def update(frame: int) -> None:
        time = times[frame]
        for agent, (sample_positions, _, sample_times) in enumerate(samples):
            trail = np.vstack((sample_positions[sample_times <= time], positions[frame, agent]))
            trails[agent].set_data(trail.T)
            markers[agent].set_data(positions[frame, agent, :, None])
        _update_links(links, positions[frame], time)
        clock.set_text(f"Mission time: {time:.2f} / {horizon:.2f} s")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        animation = FuncAnimation(figure, update, frames=len(times), interval=1000 / fps)
        animation.save(destination, writer=PillowWriter(fps=fps), dpi=100)
    finally:
        plt.close(figure)
    return destination
