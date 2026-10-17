"""Render exact saved motion pieces with path color encoding speed magnitude."""

import numpy as np
from matplotlib import colormaps
from matplotlib.cm import ScalarMappable
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize


AGENT_STYLES = ("solid", "dashed", "dotted", "dashdot")
AGENT_COLORMAPS = ("Blues", "Oranges", "Greens", "Purples", "Reds", "Greys")


def draw_task_markers(ax, tasks, reached_tasks, color_by_reward=False):
    """Use diamonds for collected tasks and circles for uncollected tasks."""
    reached = set(reached_tasks)
    collected = [task for task in tasks if task["id"] in reached]
    uncollected = [task for task in tasks if task["id"] not in reached]
    if color_by_reward and tasks:
        rewards = [task["reward"] for task in tasks]
        norm = Normalize(vmin=min(rewards), vmax=max(rewards) if max(rewards) > min(rewards) else min(rewards) + 1)
        for group, marker, size, label, alpha in (
            (uncollected, "o", 28, "Uncollected task", .65),
            (collected, "D", 65, "Collected task", 1.),
        ):
            if group:
                ax.scatter([task["position"][0] for task in group],
                           [task["position"][1] for task in group],
                           c=[task["reward"] for task in group], cmap="viridis", norm=norm,
                           marker=marker, s=size, alpha=alpha, edgecolors="black" if marker == "D" else "none",
                           linewidths=.5, zorder=4 if marker == "D" else 1, label=label)
        return ScalarMappable(norm=norm, cmap=colormaps["viridis"])
    for group, marker, size, color, label, order in (
        (uncollected, "o", 18, "0.72", "Uncollected task", 1),
        (collected, "D", 55, "goldenrod", "Collected task", 4),
    ):
        if group:
            ax.scatter([task["position"][0] for task in group],
                       [task["position"][1] for task in group],
                       marker=marker, s=size, color=color,
                       edgecolors="black" if marker == "D" else "none",
                       linewidths=.5, zorder=order, label=label)
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
    """Give each agent a distinct gradient under one shared speed scale."""
    sampled = [sample_trajectory(tr, samples_per_second) for tr in trajectories]
    maximum = (speed_max if speed_max is not None else
               max((np.linalg.norm(velocities, axis=1).max() for _, velocities, _ in sampled), default=0.))
    norm = Normalize(vmin=0., vmax=max(float(maximum), 1e-12))
    scales = []
    for local_agent, (positions, velocities, _) in enumerate(sampled):
        agent = agent_offset + local_agent
        palette = colormaps[AGENT_COLORMAPS[agent % len(AGENT_COLORMAPS)]]
        cmap = LinearSegmentedColormap.from_list(
            f"agent_{agent + 1}_speed", palette(np.linspace(.35, .95, 256)))
        scales.append(ScalarMappable(norm=norm, cmap=cmap))
        if len(positions) > 1:
            segments = np.stack((positions[:-1], positions[1:]), axis=1)
            # Midpoint velocity is exact for a constant-acceleration piece.
            segment_speeds = np.linalg.norm((velocities[:-1] + velocities[1:]) / 2, axis=1)
            collection = LineCollection(segments, cmap=cmap, norm=norm,
                                        linewidths=linewidth,
                                        linestyles=AGENT_STYLES[agent % len(AGENT_STYLES)],
                                        zorder=3)
            collection.set_array(segment_speeds)
            ax.add_collection(collection)
        else:
            ax.scatter(*positions[0], color=cmap(norm(np.linalg.norm(velocities[0]))), s=20, zorder=3)
        ax.plot([], [], color=cmap(.7), linestyle=AGENT_STYLES[agent % len(AGENT_STYLES)],
                linewidth=linewidth, label=f"Agent {agent + 1}")
    ax.autoscale_view()
    return sampled, scales


def add_speed_colorbars(fig, ax, scales):
    """Place distinct palettes in a shared horizontal speed-key panel."""
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
    scales = []
    tasks = problem["tasks"]
    for agent, (ax, trajectory) in enumerate(zip(axes[0], trajectories)):
        draw_task_markers(ax, tasks, reached_tasks)
        _, agent_scales = draw_speed_paths(ax, [trajectory], agent_offset=agent,
                                           speed_max=maximum)
        scales.extend(agent_scales)
        ax.scatter(*problem["start"], marker="s", color="black", s=35, zorder=4)
        ax.scatter(*problem["end"], marker="*", color="black", s=65, zorder=4)
        ax.set(title=f"Agent {agent + 1}", xlabel="x (m)", ylabel="y (m)")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=.2)
        if agent == 0:
            ax.legend(fontsize=7)
    add_speed_colorbars(fig, axes[0][0], scales)
    fig.savefig(Path(destination), dpi=150)
    plt.close(fig)
