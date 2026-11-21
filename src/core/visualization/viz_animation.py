"""Animate saved trajectories with the white TOP-CC paper layout."""

from pathlib import Path

import numpy as np
from matplotlib import gridspec
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.collections import LineCollection

from .viz_paths import (
    ARTICLE_COLORS,
    agent_colors_at_times,
    communication_rssi_history,
    draw_task_markers,
    maximum_trajectory_speed,
)


def _active_links(axis, solution, positions, time):
    labelled = False
    for contact in (solution.get("communication") or {}).get("contacts", []):
        if not any(start <= time <= end for start, end in contact["effective"]):
            continue
        first, second = contact["agents"]
        axis.plot(
            [positions[first, 0], positions[second, 0]],
            [positions[first, 1], positions[second, 1]],
            color="black",
            linestyle=":",
            linewidth=2,
            label="Effective communication" if not labelled else None,
            zorder=6,
        )
        labelled = True


def save_path_animation(
    problem: dict,
    solution: dict,
    output_path: str | Path,
    fps: int = 15,
    playback_seconds: float = 12.0,
    communication_rssi_threshold: float | None = None,
) -> Path:
    if fps <= 0 or playback_seconds <= 0:
        raise ValueError("Animation fps and playback duration must be positive")
    horizon = max(route["completion_time"] for route in solution["trajectories"])
    times = np.linspace(0.0, horizon, max(2, round(fps * playback_seconds) + 1))
    positions, rssi_history = communication_rssi_history(
        solution["trajectories"], times
    )
    finite_rssi = rssi_history[np.isfinite(rssi_history)]
    minimum_rssi = float(np.min(finite_rssi)) if len(finite_rssi) else float("nan")
    collection_times = {
        task_id: float(time)
        for task_id, _, time in solution.get("first_visitors", [])
    }
    maximum_speed = maximum_trajectory_speed(solution["trajectories"])
    communication = solution.get("communication")
    agent_count = len(solution["trajectories"])

    figure = plt.figure(figsize=(16, 8), facecolor="white")
    layout = gridspec.GridSpec(
        2,
        2,
        figure=figure,
        height_ratios=(1, 1),
        width_ratios=(1.5, 1),
        hspace=0.45,
        wspace=0.45,
    )
    path_axis = figure.add_subplot(layout[:, 0])
    legend_axis = figure.add_subplot(layout[0, 1])
    communication_axis = figure.add_subplot(layout[1, 1])
    reward_scale = draw_task_markers(path_axis, problem["tasks"], set(), True)
    if reward_scale is not None:
        colorbar = figure.colorbar(reward_scale, ax=path_axis, shrink=0.78)
        colorbar.set_label("Reward Value", fontsize=14)
        colorbar.ax.tick_params(labelsize=11)

    x_values = [problem["start"][0], problem["end"][0]] + [
        task["position"][0] for task in problem["tasks"]
    ]
    y_values = [problem["start"][1], problem["end"][1]] + [
        task["position"][1] for task in problem["tasks"]
    ]
    x_margin = max(1.0, (max(x_values) - min(x_values)) * 0.05)
    y_margin = max(1.0, (max(y_values) - min(y_values)) * 0.05)

    def update(frame):
        time = times[frame]
        visited = {
            task_id for task_id, arrival in collection_times.items() if arrival <= time
        }
        path_axis.clear()
        draw_task_markers(path_axis, problem["tasks"], visited, True)
        path_axis.scatter(
            *problem["start"], marker="s", color="#ff6361", edgecolors="black",
            s=130, label="Start", zorder=7,
        )
        path_axis.scatter(
            *problem["end"], marker="X", color="#58508d", edgecolors="black",
            s=130, label="Goal", zorder=7,
        )
        for agent in range(positions.shape[1]):
            trail = positions[: frame + 1, agent]
            current_color = agent_colors_at_times(
                agent,
                [time],
                solution["trajectories"][agent],
                communication,
                agent_count,
                maximum_speed,
            )[0]
            if len(trail) > 1:
                midpoints = (times[:frame] + times[1:frame + 1]) / 2
                trail_colors = agent_colors_at_times(
                    agent,
                    midpoints,
                    solution["trajectories"][agent],
                    communication,
                    agent_count,
                    maximum_speed,
                )
                path_axis.add_collection(LineCollection(
                    np.stack([trail[:-1], trail[1:]], axis=1),
                    colors=trail_colors,
                    linewidths=5,
                    zorder=3,
                ))
            path_axis.plot(
                [], [], color=ARTICLE_COLORS[agent % len(ARTICLE_COLORS)],
                linewidth=5, label=f"Agent {agent + 1}",
            )
            path_axis.scatter(*trail[-1], color=current_color, s=55, zorder=5)
            if len(trail) > 1:
                direction = trail[-1] - trail[-2]
                length = np.linalg.norm(direction)
                if length > 1e-12:
                    direction = 0.5 * direction / length
                    path_axis.quiver(
                        trail[-2, 0], trail[-2, 1], direction[0], direction[1],
                        angles="xy", scale_units="xy", scale=1,
                        color=current_color,
                        width=0.01, headlength=20, headwidth=20,
                        headaxislength=19, zorder=5,
                    )
        _active_links(path_axis, solution, positions[frame], time)
        path_axis.set(
            xlim=(min(x_values) - x_margin, max(x_values) + x_margin),
            ylim=(min(y_values) - y_margin, max(y_values) + y_margin),
            xlabel="x (m)",
            ylabel="y (m)",
            title=(
                f"R: {solution['reward']:g} | MIN RSSI: {minimum_rssi:.2f} | "
                f"T: {solution['objectives'][1]:.2f} s"
            ),
        )
        path_axis.set_aspect("equal", adjustable="box")
        path_axis.grid(True, alpha=0.35)
        path_axis.set_facecolor("white")

        communication_axis.clear()
        if len(finite_rssi):
            communication_axis.plot(
                times[: frame + 1], rssi_history[: frame + 1],
                color="red", alpha=0.7, linewidth=5,
            )
            if communication_rssi_threshold is not None:
                communication_axis.axhline(
                    communication_rssi_threshold,
                    color="#e67e22",
                    linestyle="--",
                    linewidth=2.5,
                    label="Acceptable communication threshold",
                )
                communication_axis.legend(loc="lower right", fontsize=9)
            lower_limit = min(
                minimum_rssi,
                communication_rssi_threshold
                if communication_rssi_threshold is not None
                else minimum_rssi,
            )
            communication_axis.set_ylim(lower_limit - 1, 0)
            communication_axis.set_title(
                f"RSSI: {rssi_history[frame]:.2f}", fontsize=16
            )
        else:
            communication_axis.text(
                0.5, 0.5, "Single agent", ha="center", va="center"
            )
            communication_axis.set_title("RSSI")
        communication_axis.set(
            xlim=(0, horizon), xlabel="Mission time (s)", ylabel="RSSI (dBm)"
        )
        communication_axis.grid(True, alpha=0.2)
        communication_axis.set_facecolor("white")

        legend_axis.clear()
        legend_axis.axis("off")
        handles, labels = path_axis.get_legend_handles_labels()
        legend_axis.legend(handles, labels, loc="center", fontsize=12)

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        animation = FuncAnimation(
            figure, update, frames=len(times), interval=1000 / fps
        )
        animation.save(destination, writer=PillowWriter(fps=fps), dpi=100)
    finally:
        plt.close(figure)
    return destination
