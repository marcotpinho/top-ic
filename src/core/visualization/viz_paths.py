"""Render exact saved motion pieces with path color encoding speed magnitude."""

import numpy as np
from matplotlib import colormaps
from matplotlib.cm import ScalarMappable
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize, to_rgb

from ..evaluation.rssi import rssi


AGENT_STYLES = ("solid", "dashed", "dotted", "dashdot")
AGENT_COLORMAPS = ("Blues", "Oranges", "Greens", "Purples", "Reds", "Greys")
ARTICLE_COLORS = (
    "#d62728",
    "#1f77b4",
    "#2ca02c",
    "#9467bd",
    "#8c564b",
    "#17becf",
    "#7f7f7f",
)
COMMUNICATION_COLORS = (
    "#e67e22",
    "#f1c40f",
    "#ff9f43",
    "#d9a400",
    "#f5b041",
    "#f4d03f",
)


def draw_task_markers(ax, tasks, reached_tasks, color_by_reward=False):
    """Draw rewards with the marker and color scheme used by TOP-CC."""
    reached = set(reached_tasks)
    collected = [task for task in tasks if task["id"] in reached]
    uncollected = [task for task in tasks if task["id"] not in reached]
    if tasks:
        rewards = [task["reward"] for task in tasks]
        norm = Normalize(
            vmin=min(1.0, min(rewards)), vmax=max(10.0, max(rewards))
        )
        if uncollected:
            ax.scatter(
                [task["position"][0] for task in uncollected],
                [task["position"][1] for task in uncollected],
                c=[task["reward"] for task in uncollected],
                cmap="viridis",
                norm=norm,
                marker="D",
                s=110,
                edgecolors="black",
                linewidths=.7,
                zorder=2,
                label="PoI",
            )
        if collected:
            ax.scatter(
                [task["position"][0] for task in collected],
                [task["position"][1] for task in collected],
                color="#58508d",
                marker="o",
                s=110,
                edgecolors="black",
                linewidths=.7,
                zorder=4,
                label="Visited PoI",
            )
        return ScalarMappable(norm=norm, cmap=colormaps["viridis"])
    return None


def sample_trajectory(trajectory, samples_per_second=20):
    """Sample quadratic position and linear velocity at the same timestamps."""
    positions = []
    velocities = []
    times = []
    for index, piece in enumerate(trajectory["pieces"]):
        duration = piece["duration"]
        local = np.linspace(0, duration, max(3, int(np.ceil(duration * samples_per_second)) + 1))
        if index:
            local = local[1:]  # the preceding piece already supplied this endpoint
        position = np.asarray(piece["position"], dtype=float)
        velocity = np.asarray(piece["velocity"], dtype=float)
        acceleration = np.asarray(piece["acceleration"], dtype=float)
        positions.extend(position + local[:, None] * velocity + .5 * local[:, None] ** 2 * acceleration)
        velocities.extend(velocity + local[:, None] * acceleration)
        times.extend(piece["start_time"] + local)
    if not positions:
        positions = [trajectory["start"]["position"]]
        velocities = [trajectory["start"]["velocity"]]
        times = [0.]
    return np.asarray(positions), np.asarray(velocities), np.asarray(times)


def positions_at_times(trajectory, times):
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


def velocities_at_times(trajectory, times):
    velocities = np.zeros((len(times), 2), dtype=float)
    for piece in trajectory["pieces"]:
        local = times - piece["start_time"]
        active = (local >= 0) & (local <= piece["duration"])
        elapsed = local[active, None]
        velocities[active] = (
            np.asarray(piece["velocity"])
            + elapsed * np.asarray(piece["acceleration"])
        )
    return velocities


def communication_components(communication, time, agent_count):
    adjacency = [set() for _ in range(agent_count)]
    for contact in (communication or {}).get("contacts", []):
        if not any(start <= time <= end for start, end in contact.get("effective", [])):
            continue
        first, second = contact["agents"]
        adjacency[first].add(second)
        adjacency[second].add(first)
    components = []
    pending = {agent for agent, neighbors in enumerate(adjacency) if neighbors}
    while pending:
        stack = [min(pending)]
        component = set()
        while stack:
            agent = stack.pop()
            if agent in component:
                continue
            component.add(agent)
            stack.extend(adjacency[agent] - component)
        pending -= component
        components.append(tuple(sorted(component)))
    return sorted(components)


def _speed_color(color, velocity, maximum_speed):
    ratio = min(1.0, float(np.linalg.norm(velocity)) / maximum_speed)
    white_fraction = 0.58 * (1.0 - ratio)
    rgb = np.asarray(to_rgb(color))
    return tuple(rgb * (1.0 - white_fraction) + white_fraction)


def agent_color_at_time(
    agent, time, communication, agent_count, velocity, maximum_speed
):
    base = ARTICLE_COLORS[agent % len(ARTICLE_COLORS)]
    for group_index, component in enumerate(
        communication_components(communication, time, agent_count)
    ):
        if agent in component:
            base = COMMUNICATION_COLORS[group_index % len(COMMUNICATION_COLORS)]
            break
    return _speed_color(base, velocity, maximum_speed)


def maximum_trajectory_speed(trajectories):
    maximum = max(
        (
            float(np.linalg.norm(velocity))
            for trajectory in trajectories
            for piece in trajectory["pieces"]
            for velocity in (
                np.asarray(piece["velocity"]),
                np.asarray(piece["velocity"])
                + piece["duration"] * np.asarray(piece["acceleration"]),
            )
        ),
        default=0.0,
    )
    return max(maximum, np.finfo(float).eps)


def agent_colors_at_times(
    agent, times, trajectory, communication, agent_count, maximum_speed
):
    velocities = velocities_at_times(trajectory, np.asarray(times))
    return [
        agent_color_at_time(
            agent,
            float(time),
            communication,
            agent_count,
            velocity,
            maximum_speed,
        )
        for time, velocity in zip(times, velocities)
    ]


def communication_rssi_history(trajectories, times):
    positions = np.stack(
        [positions_at_times(trajectory, times) for trajectory in trajectories], axis=1
    )
    if positions.shape[1] < 2:
        return positions, np.full(len(times), np.nan)
    maximum_distances = np.zeros(len(times))
    for first in range(positions.shape[1]):
        for second in range(first + 1, positions.shape[1]):
            distances = np.linalg.norm(
                positions[:, first] - positions[:, second], axis=1
            )
            maximum_distances = np.maximum(maximum_distances, distances)
    return positions, np.asarray([rssi(float(distance)) for distance in maximum_distances])


def draw_speed_paths(ax, trajectories, samples_per_second=20, linewidth=3,
                     agent_offset=0, speed_max=None, communication=None,
                     agent_count=None):
    """Draw continuous trajectories with the path style used by TOP-CC."""
    sampled = [sample_trajectory(tr, samples_per_second) for tr in trajectories]
    total_agents = agent_count or len(trajectories)
    maximum_speed = speed_max or maximum_trajectory_speed(trajectories)
    for local_agent, (positions, _, times) in enumerate(sampled):
        agent = agent_offset + local_agent
        color = ARTICLE_COLORS[agent % len(ARTICLE_COLORS)]
        if len(positions) > 1:
            midpoints = (times[:-1] + times[1:]) / 2
            segment_colors = agent_colors_at_times(
                agent,
                midpoints,
                trajectories[local_agent],
                communication,
                total_agents,
                maximum_speed,
            )
            segments = np.stack([positions[:-1], positions[1:]], axis=1)
            ax.add_collection(LineCollection(
                segments,
                colors=segment_colors,
                linewidths=max(5, linewidth),
                zorder=3,
            ))
            ax.plot([], [], color=color, linewidth=max(5, linewidth),
                    label=f"Agent {agent + 1}")
            deltas = np.diff(positions, axis=0)
            lengths = np.linalg.norm(deltas, axis=1)
            moving = np.flatnonzero(lengths > 1e-12)
            if len(moving):
                picks = moving[
                    np.unique(np.linspace(0, len(moving) - 1, min(8, len(moving))).astype(int))
                ]
                directions = deltas[picks] / lengths[picks, None]
                ax.quiver(
                    positions[picks, 0],
                    positions[picks, 1],
                    0.5 * directions[:, 0],
                    0.5 * directions[:, 1],
                    angles="xy",
                    scale_units="xy",
                    scale=1,
                    color=[segment_colors[pick] for pick in picks],
                    width=0.007,
                    headlength=8,
                    headwidth=7,
                    headaxislength=7,
                    zorder=4,
                )
        else:
            ax.scatter(*positions[0], color=color, s=20, zorder=3)
    ax.autoscale_view()
    return sampled, []


def add_speed_colorbars(fig, ax, scales):
    """Place distinct palettes in a shared horizontal speed-key panel."""
    if not scales:
        fig.tight_layout()
        return
    reserve = min(.35, .08 + .045 * len(scales))
    fig.tight_layout(rect=(0, reserve, 1, 0.94))
    for agent, scale in enumerate(scales):
        y = reserve - .05 - .045 * agent
        fig.text(.09, y + .008, f"Agent {agent + 1}", va="center", fontsize=8)
        bar = fig.colorbar(scale, cax=fig.add_axes((.19, y, .68, .016)),
                           orientation="horizontal")
        if agent == len(scales) - 1:
            bar.set_label("Speed (m/s)", fontsize=8)
            bar.ax.tick_params(labelsize=7)
        else:
            bar.ax.set_xticklabels([])


def save_agent_path_panels(
    problem, trajectories, destination, reached_tasks=(), communication=None
):
    """Show coincident routes separately without changing their coordinates."""
    from pathlib import Path
    from matplotlib import pyplot as plt

    if not trajectories:
        return
    sampled = [sample_trajectory(trajectory) for trajectory in trajectories]
    maximum = max(float(np.linalg.norm(velocities, axis=1).max())
                  for _, velocities, _ in sampled)
    n = len(trajectories)
    fig, axes = plt.subplots(1, n, figsize=(max(6, 4*n), 5), squeeze=False,
                             sharex=True, sharey=True)
    tasks = problem["tasks"]
    for agent, (ax, trajectory) in enumerate(zip(axes[0], trajectories)):
        draw_task_markers(ax, tasks, reached_tasks, color_by_reward=True)
        draw_speed_paths(
            ax,
            [trajectory],
            agent_offset=agent,
            speed_max=maximum,
            communication=communication,
            agent_count=n,
        )
        ax.scatter(*problem["start"], marker="s", color="#ff6361", edgecolors="black", s=100, zorder=5)
        ax.scatter(*problem["end"], marker="X", color="#58508d", edgecolors="black", s=100, zorder=5)
        ax.set_facecolor("white")
        ax.set(title=f"Agent {agent + 1}", xlabel="x (m)", ylabel="y (m)")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=.2)
        if agent == 0:
            ax.legend(fontsize=7)
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    fig.savefig(Path(destination), dpi=150)
    plt.close(fig)
