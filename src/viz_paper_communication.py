"""Paper-ready trajectory and temporal-contact figures from saved results."""

from argparse import ArgumentParser
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np


AGENT_COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7")
CONTACT_COLOR = "#009E73"
ABSENT_COLOR = "#C44E52"


def _style():
    plt.rcParams.update(
        {
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 8,
            "legend.fontsize": 7,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "lines.linewidth": 1.4,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
        }
    )


def _load(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def _representative(data):
    maximum = max(solution["reward"] for solution in data["front"])
    options = [solution for solution in data["front"] if solution["reward"] == maximum]
    return min(options, key=lambda solution: np.mean(solution["completion_times"]))


def _state_position(trajectory, time):
    if time >= trajectory["completion_time"]:
        return np.asarray(trajectory["end"]["position"], dtype=float)
    for piece in trajectory["pieces"]:
        start = piece["start_time"]
        end = start + piece["duration"]
        if start - 1e-9 <= time <= end + 1e-9:
            local = min(piece["duration"], max(0.0, time - start))
            position = np.asarray(piece["position"], dtype=float)
            velocity = np.asarray(piece["velocity"], dtype=float)
            acceleration = np.asarray(piece["acceleration"], dtype=float)
            return position + velocity * local + 0.5 * acceleration * local * local
    return np.asarray(trajectory["start"]["position"], dtype=float)


def _sample(trajectory, count=500):
    horizon = trajectory["completion_time"]
    times = np.linspace(0.0, horizon, count)
    positions = np.asarray([_state_position(trajectory, time) for time in times])
    return times, positions


def _record(solution, pair):
    normalized = tuple(sorted(pair))
    for record in solution["communication"]["contacts"]:
        if tuple(sorted(record["agents"])) == normalized:
            return record
    raise ValueError(f"Missing contact pair {normalized}")


def _inside(time, intervals):
    return any(start - 1e-9 <= time <= end + 1e-9 for start, end in intervals)


def _covers(intervals, start, end):
    cursor = start
    for left, right in sorted(intervals):
        if right < cursor - 1e-9:
            continue
        if left > cursor + 1e-9:
            return False
        cursor = max(cursor, right)
        if cursor >= end - 1e-9:
            return True
    return cursor >= end - 1e-9


def _complement(intervals, horizon):
    gaps = []
    cursor = 0.0
    for start, end in sorted(intervals):
        start = max(0.0, start)
        end = min(horizon, end)
        if start > cursor + 1e-9:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < horizon - 1e-9:
        gaps.append((cursor, horizon))
    return gaps


def _draw_tasks(ax, problem, solution):
    reached = set().union(*(set(tasks) for tasks in solution["reached_tasks"]))
    collected = [task for task in problem["tasks"] if task["id"] in reached]
    uncollected = [task for task in problem["tasks"] if task["id"] not in reached]
    if uncollected:
        ax.scatter(
            [task["position"][0] for task in uncollected],
            [task["position"][1] for task in uncollected],
            s=9,
            color="0.72",
            zorder=1,
        )
    if collected:
        ax.scatter(
            [task["position"][0] for task in collected],
            [task["position"][1] for task in collected],
            s=23,
            marker="D",
            facecolor="#E69F00",
            edgecolor="black",
            linewidth=0.35,
            zorder=5,
        )


def _draw_routes(ax, data, solution):
    _draw_tasks(ax, data["problem"], solution)
    sampled = []
    for agent, trajectory in enumerate(solution["trajectories"]):
        times, positions = _sample(trajectory)
        sampled.append((times, positions))
        ax.plot(
            positions[:, 0],
            positions[:, 1],
            color=AGENT_COLORS[agent],
            label=f"Agent {agent + 1}",
            zorder=3,
        )
    start = data["problem"]["start"]
    end = data["problem"]["end"]
    ax.scatter(*start, marker="s", s=25, color="black", zorder=6)
    ax.scatter(*end, marker="*", s=42, color="black", zorder=6)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(color="0.88", linewidth=0.45)
    return sampled


def _draw_contact_on_routes(ax, solution, pair=(0, 1)):
    intervals = _record(solution, pair)["raw"]
    duration = max(solution["completion_times"])
    times = np.linspace(0.0, duration, 420)
    contact_times = [time for time in times if _inside(time, intervals)]
    for agent in pair:
        positions = np.asarray(
            [_state_position(solution["trajectories"][agent], time) for time in contact_times]
        )
        if len(positions):
            ax.scatter(
                positions[:, 0],
                positions[:, 1],
                s=5,
                facecolor=CONTACT_COLOR,
                edgecolor="white",
                linewidth=0.15,
                alpha=0.75,
                zorder=4,
            )
    for start, end in intervals:
        if end - start <= 1e-8:
            continue
        for time in np.linspace(start, end, 4)[1:-1]:
            first = _state_position(solution["trajectories"][pair[0]], time)
            second = _state_position(solution["trajectories"][pair[1]], time)
            ax.plot(
                [first[0], second[0]],
                [first[1], second[1]],
                color=CONTACT_COLOR,
                alpha=0.25,
                linewidth=0.7,
                zorder=2,
            )


def plot_tc_sweep(result_paths, destination):
    data = [_load(path) for path in result_paths]
    solutions = [_representative(result) for result in data]
    figure, axes = plt.subplots(1, 3, figsize=(7.16, 2.42), sharex=True, sharey=True)
    labels = ("(a)", "(b)", "(c)")
    for label, ax, result, solution in zip(labels, axes, data, solutions):
        _draw_routes(ax, result, solution)
        _draw_contact_on_routes(ax, solution)
        tc = result["config"]["recurrence_bound"]
        delta = solution["peak_staleness"]
        ax.set_title(
            rf"{label} $T_c={tc:g}$ s; $Q={solution['reward']:g}$; $\Delta={delta:.2f}$ s"
        )
        ax.set_xlabel("$x$ (m)")
    axes[0].set_ylabel("$y$ (m)")
    handles = [
        Line2D([], [], color=AGENT_COLORS[0], label="Agent 1"),
        Line2D([], [], color=AGENT_COLORS[1], label="Agent 2"),
        Line2D(
            [],
            [],
            marker="o",
            linestyle="none",
            markersize=4,
            markerfacecolor=CONTACT_COLOR,
            markeredgecolor="white",
            label="In-range path portion",
        ),
        Line2D(
            [],
            [],
            marker="D",
            linestyle="none",
            markersize=4,
            markerfacecolor="#E69F00",
            markeredgecolor="black",
            label="Collected task",
        ),
    ]
    figure.legend(handles=handles, loc="lower center", ncol=4, frameon=False)
    figure.subplots_adjust(left=0.065, right=0.995, top=0.88, bottom=0.23, wspace=0.12)
    _save(figure, destination)


def _indirect_interval(solution):
    horizon = max(solution["completion_times"])
    agents = range(len(solution["trajectories"]))
    candidates = []
    for first in agents:
        for second in range(first + 1, len(solution["trajectories"])):
            relay = next(agent for agent in agents if agent not in (first, second))
            direct = _record(solution, (first, second))["raw"]
            first_relay = _record(solution, (first, relay))["raw"]
            second_relay = _record(solution, (second, relay))["raw"]
            for start, end in _complement(direct, horizon):
                if _covers(first_relay, start, end) and _covers(second_relay, start, end):
                    candidates.append((end - start, start, end, first, second, relay))
    if not candidates:
        raise ValueError("No indirect-only interval found")
    return max(candidates)


def plot_indirect_communication(result_path, destination):
    data = _load(result_path)
    solution = _representative(data)
    _, start, end, first, second, relay = _indirect_interval(solution)
    instant = (start + end) / 2
    figure, (path_ax, time_ax) = plt.subplots(
        1, 2, figsize=(7.16, 2.72), gridspec_kw={"width_ratios": (1.12, 1)}
    )
    _draw_routes(path_ax, data, solution)
    positions = [
        _state_position(trajectory, instant) for trajectory in solution["trajectories"]
    ]
    for agent, position in enumerate(positions):
        path_ax.scatter(
            *position,
            s=38,
            color=AGENT_COLORS[agent],
            edgecolor="white",
            linewidth=0.7,
            zorder=8,
        )
        path_ax.annotate(
            str(agent + 1),
            position,
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=7,
            weight="bold",
        )
    for agent in (first, second):
        path_ax.plot(
            [positions[relay][0], positions[agent][0]],
            [positions[relay][1], positions[agent][1]],
            color=CONTACT_COLOR,
            linewidth=1.6,
            zorder=7,
        )
    path_ax.plot(
        [positions[first][0], positions[second][0]],
        [positions[first][1], positions[second][1]],
        color=ABSENT_COLOR,
        linestyle="--",
        linewidth=1.1,
        zorder=6,
    )
    path_ax.set(
        title=rf"(a) Paths and links at $t={instant:.2f}$ s",
        xlabel="$x$ (m)",
        ylabel="$y$ (m)",
    )
    records = sorted(
        solution["communication"]["contacts"], key=lambda item: tuple(item["agents"])
    )
    for row, record in enumerate(records):
        for left, right in record["raw"]:
            time_ax.broken_barh(
                [(left, right - left)],
                (row - 0.28, 0.56),
                facecolors=CONTACT_COLOR,
                edgecolors="none",
            )
    time_ax.axvspan(start, end, color=ABSENT_COLOR, alpha=0.13)
    time_ax.axvline(instant, color="black", linestyle=":", linewidth=0.9)
    time_ax.set(
        title="(b) Direct contact intervals",
        xlabel="Mission time (s)",
        ylabel="Agent pair",
        yticks=range(len(records)),
        yticklabels=[
            f"{record['agents'][0] + 1}--{record['agents'][1] + 1}"
            for record in records
        ],
        xlim=(0.0, max(solution["completion_times"])),
        ylim=(-0.6, len(records) - 0.4),
    )
    time_ax.grid(axis="x", color="0.88", linewidth=0.45)
    time_ax.text(
        (start + end) / 2,
        len(records) - 0.52,
        rf"indirect only: {end - start:.2f} s",
        color=ABSENT_COLOR,
        ha="center",
        va="top",
        fontsize=7,
    )
    handles = [
        Line2D([], [], color=CONTACT_COLOR, linewidth=2, label="Direct link present"),
        Line2D(
            [], [], color=ABSENT_COLOR, linestyle="--", label="External direct link absent"
        ),
    ]
    figure.legend(handles=handles, loc="lower center", ncol=2, frameon=False)
    figure.subplots_adjust(left=0.075, right=0.995, top=0.88, bottom=0.23, wspace=0.28)
    _save(figure, destination)


def _save(figure, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination.with_suffix(".pdf"))
    figure.savefig(destination.with_suffix(".png"), dpi=400)
    plt.close(figure)


def main():
    parser = ArgumentParser()
    parser.add_argument("--tc-results", nargs=3, required=True)
    parser.add_argument("--indirect-result", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("paper/figures"))
    arguments = parser.parse_args()
    _style()
    plot_tc_sweep(arguments.tc_results, arguments.output_dir / "tc-contact-sweep")
    plot_indirect_communication(
        arguments.indirect_result, arguments.output_dir / "indirect-communication"
    )


if __name__ == "__main__":
    main()
