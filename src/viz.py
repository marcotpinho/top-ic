"""Portable Pareto and continuous trajectory plots for saved KOP results."""

import json
from pathlib import Path

from matplotlib import pyplot as plt

from .viz_paths import (
    add_speed_colorbars,
    draw_speed_paths,
    draw_task_markers,
    save_agent_path_panels,
)


def plot_execution_time(data: dict, output_dir: Path, elapsed_seconds: float) -> None:
    """Draw disjoint timing regions with area and color proportional to seconds."""
    from matplotlib import pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.patches import Rectangle

    profile = data.get("statistics", {}).get("profiling", {})
    timings = [
        (name, float(row.get("total_seconds", 0)))
        for name, row in profile.get("neighborhoods", {}).items()
        if row.get("total_seconds", 0) > 0
    ]
    neighborhood_seconds = sum(seconds for _, seconds in timings)
    loop_seconds = max(
        float(profile.get("search_loop_seconds", 0)), neighborhood_seconds
    )
    timings.extend(
        [
            ("Other search work", max(0.0, loop_seconds - neighborhood_seconds)),
            (
                "Initialization / CLI / result serialization",
                max(0.0, elapsed_seconds - loop_seconds),
            ),
        ]
    )
    timings = sorted(
        [(name, seconds) for name, seconds in timings if seconds > 0],
        key=lambda row: row[1], reverse=True,
    )
    fig, (ax, legend) = plt.subplots(
        1, 2, figsize=(15, 8), gridspec_kw={"width_ratios": [1.5, 1]},
        layout="constrained",
    )
    ax.set(xlim=(0, 1), ylim=(0, 1), aspect="equal")
    ax.axis("off")
    legend.axis("off")
    fig.suptitle("Execution time — area and color proportional to duration")
    if not timings:
        ax.text(0.5, 0.5, "No execution timing available", ha="center", va="center")
    else:
        total_seconds = sum(seconds for _, seconds in timings)
        norm = Normalize(vmin=0, vmax=timings[0][1])
        cmap = plt.get_cmap("YlOrRd")

        def draw(rows, x, y, width, height):
            if len(rows) == 1:
                index, (_, seconds) = rows[0]
                color = cmap(norm(seconds))
                ax.add_patch(Rectangle(
                    (x, y), width, height, facecolor=color,
                    edgecolor="white", linewidth=1.5,
                ))
                if width > 0.055 and height > 0.055:
                    ax.text(
                        x + width / 2, y + height / 2, str(index),
                        ha="center", va="center", fontsize=11,
                        color="white" if norm(seconds) > 0.55 else "black",
                    )
                return
            subtotal = sum(row[1][1] for row in rows)
            split = min(
                range(1, len(rows)),
                key=lambda i: abs(sum(row[1][1] for row in rows[:i]) - subtotal / 2),
            )
            fraction = sum(row[1][1] for row in rows[:split]) / subtotal
            if width >= height:
                draw(rows[:split], x, y, width * fraction, height)
                draw(rows[split:], x + width * fraction, y, width * (1 - fraction), height)
            else:
                draw(rows[:split], x, y, width, height * fraction)
                draw(rows[split:], x, y + height * fraction, width, height * (1 - fraction))

        draw(list(enumerate(timings, 1)), 0, 0, 1, 1)
        for index, (name, seconds) in enumerate(timings, 1):
            y = 1 - index / (len(timings) + 1)
            legend.add_patch(Rectangle(
                (0, y - 0.012), 0.035, 0.025,
                facecolor=cmap(norm(seconds)), transform=legend.transAxes,
            ))
            legend.text(
                0.05, y, f"{index}. {name}\n{seconds:.3f} s ({seconds / total_seconds:.1%})",
                va="center", transform=legend.transAxes, fontsize=9,
            )
        fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax,
                     shrink=0.7, label="Duration (s)")
        fig.supxlabel(
            f"CLI total: {elapsed_seconds:.3f} s. "
            "Neighborhood totals include generation and evaluation.\n"
            "Other search work includes repair and archive management; plot generation is excluded.",
            fontsize=9,
        )
    try:
        fig.savefig(output_dir / "execution-time-heatmap.png", dpi=180)
    finally:
        plt.close(fig)


def select_path_representatives(data):
    """Choose three reproducible views from the configured-Tc reward/time front."""
    front = data["front"]
    tc = data.get("config", {}).get("recurrence_bound")
    slice_row = next(
        (row for row in data.get("tc_slices", []) if row["tc"] == tc), None
    )
    if slice_row is not None:
        indices = list(slice_row["front_indices"])
    else:
        indices = list(range(len(front)))
    if not indices:
        return {}
    productive = [i for i in indices if front[i]["reward"] > 0]
    if productive:
        indices = productive
    highest = max(
        indices, key=lambda i: (front[i]["reward"], -front[i]["objectives"][1], -i)
    )
    conservative = min(
        indices, key=lambda i: (front[i]["objectives"][1], -front[i]["reward"], i)
    )
    rewards = [front[i]["reward"] for i in indices]
    times = [front[i]["objectives"][1] for i in indices]
    rmin, rmax = min(rewards), max(rewards)
    tmin, tmax = min(times), max(times)
    middle = [i for i in indices if i not in (highest, conservative)] or indices

    def tradeoff_score(i):
        reward_shortfall = (
            (rmax - front[i]["reward"]) / (rmax - rmin) if rmax > rmin else 0.0
        )
        time_excess = (
            (front[i]["objectives"][1] - tmin) / (tmax - tmin) if tmax > tmin else 0.0
        )
        return (
            reward_shortfall**2 + time_excess**2,
            -front[i]["reward"],
            front[i]["objectives"][1],
            i,
        )

    tradeoff = min(middle, key=tradeoff_score)
    return {"max-reward": highest, "tradeoff": tradeoff, "conservative": conservative}


def _position_at(trajectory, time):
    """Evaluate one saved quadratic trajectory at a contact timestamp."""
    for piece in trajectory["pieces"]:
        start = piece["start_time"]
        local_time = time - start
        if -1e-9 <= local_time <= piece["duration"] + 1e-9:
            local_time = min(max(local_time, 0.0), piece["duration"])
            return [
                piece["position"][axis]
                + local_time * piece["velocity"][axis]
                + 0.5 * local_time**2 * piece["acceleration"][axis]
                for axis in range(2)
            ]
    return trajectory["end"]["position"]


def _draw_communication_links(ax, solution):
    """Overlay effective contact intervals as links between agent paths."""
    communication = solution.get("communication") or {}
    trajectories = solution.get("trajectories", [])
    labelled = False
    for contact in communication.get("contacts", []):
        first_agent, second_agent = contact["agents"]
        for start, end in contact.get("effective", []):
            midpoint = (start + end) / 2
            first_position = _position_at(trajectories[first_agent], midpoint)
            second_position = _position_at(trajectories[second_agent], midpoint)
            ax.plot(
                [first_position[0], second_position[0]],
                [first_position[1], second_position[1]],
                color="black",
                linestyle=":",
                linewidth=2.2,
                alpha=0.9,
                zorder=6,
                label="Effective communication" if not labelled else None,
            )
            ax.scatter(
                [first_position[0], second_position[0]],
                [first_position[1], second_position[1]],
                color="black",
                marker="x",
                s=35,
                zorder=7,
            )
            labelled = True


def _plot_communication(solution, output_path):
    """Plot raw/effective contact windows and the Delta history."""
    communication = solution.get("communication") or {}
    contacts = communication.get("contacts", [])
    history = communication.get("history", [])
    agent_pairs = [contact["agents"] for contact in contacts]
    figure, (contact_axis, delta_axis) = plt.subplots(
        2, 1, figsize=(10, 6), sharex=True, gridspec_kw={"height_ratios": [1, 2]}
    )
    for row, contact in enumerate(contacts):
        for start, end in contact.get("raw", []):
            contact_axis.barh(
                row,
                end - start,
                left=start,
                height=0.62,
                color="tab:blue",
                alpha=0.25,
                label="Raw in-range contact" if row == 0 else None,
            )
        for start, end in contact.get("effective", []):
            contact_axis.barh(
                row,
                end - start,
                left=start,
                height=0.34,
                color="tab:blue",
                alpha=0.9,
                label="Effective communication" if row == 0 else None,
            )
    contact_axis.set_yticks(range(len(agent_pairs)))
    contact_axis.set_yticklabels(
        [f"Agent {first + 1} ↔ {second + 1}" for first, second in agent_pairs]
    )
    contact_axis.set_ylabel("Agent pair")
    contact_axis.set_title("Communication contacts and staleness")
    if contacts:
        contact_axis.legend(loc="upper right", fontsize=8)
    if history:
        times = [row[0] for row in history]
        left_limits = [row[1] for row in history]
        exact_values = [row[2] for row in history]
        delta_axis.step(
            times,
            left_limits,
            where="post",
            color="tab:orange",
            label="Peak staleness Δ (left limit)",
        )
        delta_axis.scatter(
            times,
            exact_values,
            color="tab:green",
            s=14,
            label="Peak staleness Δ (at event)",
            zorder=3,
        )
        delta_axis.legend(loc="upper right", fontsize=8)
    delta_axis.set(xlabel="Mission time (s)", ylabel="Peak staleness Δ (s)")
    delta_axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def draw_solution_paths(
    problem, solution, title, output_path, show_communication=False
):
    """Render one saved solution with collected-task symbols and speed gradients."""
    fig, ax = plt.subplots(figsize=(10, 7))
    tasks = problem["tasks"]
    reached = set().union(*(set(ids) for ids in solution.get("reached_tasks", [])))
    task_colors = draw_task_markers(ax, tasks, reached, color_by_reward=True)
    if task_colors is not None:
        fig.colorbar(task_colors, ax=ax, shrink=0.6, label="Task reward")
    for task in tasks:
        if len(tasks) <= 30 or task["id"] in reached:
            ax.annotate(
                task["id"],
                task["position"],
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=7,
            )
    for label, key, marker in [("Start", "start", "s"), ("End", "end", "X")]:
        ax.scatter(*problem[key], marker=marker, s=100, label=label)
    sampled, speed_colors = draw_speed_paths(ax, solution["trajectories"])
    if show_communication:
        _draw_communication_links(ax, solution)
    free_label = True
    for m, route in enumerate(solution["routes"]):
        for visit in route:
            if visit["kind"] != "FREE":
                continue
            ax.scatter(
                *visit["position"],
                marker="D",
                s=100,
                facecolors="none",
                edgecolors="tab:red",
                linewidths=1.5,
                zorder=5,
                label="Free waypoint" if free_label else None,
            )
            ax.annotate(
                f"F{m + 1}",
                visit["position"],
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
            )
            free_label = False
    ax.set(
        title=f"{title}: reward {solution['reward']:g}\nMean time {solution['objectives'][1]:.3f}s; Δ {(solution.get('peak_staleness') or 0):.3f}s",
        xlabel="x (m)",
        ylabel="y (m)",
    )
    ax.set_aspect("equal")
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8)
    add_speed_colorbars(fig, ax, speed_colors)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return sampled, reached


def plot_objective_history(
    data_orpath: dict | str | Path, output_dir: str | Path
) -> Path | None:
    """Plot archived objective vectors at selected search iterations."""
    data = (
        json.loads(Path(data_orpath).read_text())
        if isinstance(data_orpath, (str, Path))
        else data_orpath
    )
    history = data.get("statistics", {}).get("objective_history")
    if not history:
        return None  # Older result files did not record iteration snapshots.
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    snapshots = [row for row in history if row.get("objectives")]
    if not snapshots:
        return None
    selected = sorted(
        {round(i * (len(snapshots) - 1) / 5) for i in range(min(6, len(snapshots)))}
    )
    fig, ax = plt.subplots(figsize=(9, 7))
    colors = plt.get_cmap("viridis")
    denominator = max(1, len(snapshots) - 1)
    for index in selected:
        row = snapshots[index]
        vectors = row["objectives"]
        ax.plot(
            [vector[1] for vector in vectors],
            [-vector[0] for vector in vectors],
            color=colors(index / denominator),
            label=f"Iteration {row['iteration']}",
            alpha=0.8,
            marker=".",
        )
    ax.set(
        xlabel="Mean completion time (s; minimize)",
        ylabel="Team reward (maximize)",
        title="Feasible archive Pareto progression by iteration",
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = out / "pareto-improvement.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_result(data_orpath, output_dir):
    """Plot saved full trajectories; no straight-line route approximation."""
    from pathlib import Path

    data = (
        json.loads(Path(data_orpath).read_text())
        if isinstance(data_orpath, (str, Path))
        else data_orpath
    )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for obsolete_plot in (
        "paths-tradeoff.png",
        "paths-max-reward-budget-only.png",
        "paths-conservative.png",
        "paths-max-reward.png",
        "representative-paths.json",
    ):
        (out / obsolete_plot).unlink(missing_ok=True)
    plot_objective_history(data, out)
    if data.get("tc_slices"):
        from .viz_sweep import plot_tc_sweep

        plot_tc_sweep(data, out)
    front = data["front"]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter([s["objectives"][1] for s in front], [s["reward"] for s in front])
    ax.set(
        xlabel="Average completion time (s; minimize)",
        ylabel="Team reward (maximize)",
        title="Epsilon-box archive representatives"
        if data.get("statistics", {}).get("archive_policy") == "epsilon_box_dominance"
        else "Nondominated solutions",
    )
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "pareto.png", dpi=150)
    plt.close(fig)
    selected = select_path_representatives(data) if front else {}
    problem = data["problem"]
    if not selected:
        return
    chosen = front[selected["max-reward"]]
    from .viz_animation import save_path_animation

    save_path_animation(problem, chosen, out / "paths-animation.gif")
    sampled, reached = draw_solution_paths(
        problem, chosen, "Maximum reward", out / "paths.png"
    )
    draw_solution_paths(
        problem,
        chosen,
        "Maximum reward with effective communication links",
        out / "paths-communication.png",
        show_communication=True,
    )
    _plot_communication(chosen, out / "communication.png")
    fig2, speed = plt.subplots(figsize=(8, 4))
    for m, (_, velocities, times) in enumerate(sampled):
        # Plot components: model has axis limits, not a Euclidean speed cap.
        speed.plot(times, velocities[:, 0], label=f"Agent {m + 1} vx")
        speed.plot(times, velocities[:, 1], linestyle="--", label=f"Agent {m + 1} vy")
    speed.set(
        xlabel="Time (s)",
        ylabel="Velocity components (m/s)",
        title="Continuous piecewise acceleration trajectory",
    )
    speed.grid(alpha=0.2)
    speed.legend(fontsize=8)
    fig2.tight_layout()
    fig2.savefig(out / "speed.png", dpi=150)
    plt.close(fig2)
    save_agent_path_panels(
        problem, chosen["trajectories"], out / "agent-paths.png", reached
    )


def plot_comparison(named_results, output_path):
    fig, ax = plt.subplots(figsize=(9, 6))
    for name, data in named_results:
        front = sorted(data["front"], key=lambda s: s["objectives"][1])
        ax.plot(
            [s["objectives"][1] for s in front],
            [s["reward"] for s in front],
            marker=".",
            label=name,
            alpha=0.8,
        )
    ax.set(
        xlabel="Average completion time (s; minimize)",
        ylabel="Reward (maximize)",
        title="Matched-budget epsilon archive fronts",
    )
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
