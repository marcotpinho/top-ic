"""Render exact saved motion pieces with path color encoding speed magnitude."""

import numpy as np
from matplotlib import colormaps
from matplotlib.cm import ScalarMappable
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize


AGENT_STYLES = ("solid", "dashed", "dotted", "dashdot")
AGENT_COLORMAPS = ("Blues", "Oranges", "Greens", "Purples", "Reds", "Greys")


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


def draw_speed_paths(ax, trajectories, samples_per_second=20, linewidth=3,
                     agent_offset=0, speed_max=None):
    """Draw continuous trajectories with the path style used by TOP-CC."""
    sampled = [sample_trajectory(tr, samples_per_second) for tr in trajectories]
    colors = colormaps["tab10"]
    for local_agent, (positions, _, _) in enumerate(sampled):
        agent = agent_offset + local_agent
        color = colors(agent % 10)
        if len(positions) > 1:
            ax.plot(
                positions[:, 0],
                positions[:, 1],
                color=color,
                linewidth=max(5, linewidth),
                zorder=3,
                label=f"Agent {agent + 1}",
            )
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
                    color=color,
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


def save_agent_path_panels(problem, trajectories, destination, reached_tasks=()):
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
        draw_speed_paths(ax, [trajectory], agent_offset=agent, speed_max=maximum)
        ax.scatter(*problem["start"], marker="s", color="#ff6361", edgecolors="black", s=100, zorder=5)
        ax.scatter(*problem["end"], marker="X", color="#58508d", edgecolors="black", s=100, zorder=5)
        ax.set_facecolor("grey")
        ax.set(title=f"Agent {agent + 1}", xlabel="x (m)", ylabel="y (m)")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=.2)
        if agent == 0:
            ax.legend(fontsize=7)
    fig.patch.set_facecolor("grey")
    fig.tight_layout()
    fig.savefig(Path(destination), dpi=150)
    plt.close(fig)
