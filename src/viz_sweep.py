"""Plots of one three-objective ICC archive and its post-run Tc slices."""

import json
from pathlib import Path

from matplotlib import pyplot as plt


def plot_tc_sweep(data, output_dir):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    front = data.get("front", [])
    slices = data.get("tc_slices", [])
    if not slices or not front:
        return
    (output / "tc-sweep.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_result": "result.json",
                "effective_epsilon": data["statistics"]["effective_epsilon"],
                "slices": slices,
            },
            indent=2,
        )
        + "\n"
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    for row in slices:
        points = sorted(
            (front[i] for i in row["front_indices"]), key=lambda s: s["objectives"][1]
        )
        if points:
            ax.plot(
                [s["objectives"][1] for s in points],
                [s["reward"] for s in points],
                marker=".",
                label=f"Tc={row['tc']} s" if row["tc"] != "infinity" else "Tc=∞",
            )
    ax.set(
        xlabel="Mean completion time (s; minimize)",
        ylabel="Team reward (maximize)",
        title="Reward–time fronts filtered from one 3D archive",
    )
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output / "tc-fronts.png", dpi=150)
    fig.savefig(output / "pareto-frontier.png", dpi=150)
    plt.close(fig)

    violation_policy = data.get("objective_policy") == "reward_time_violation"
    history = data.get("statistics", {}).get("objective_history", [])
    if history:
        chosen = next(
            (
                row["tc"]
                for row in slices
                if row["tc"] == data["config"]["recurrence_bound"]
            ),
            "infinity",
        )
        indices = sorted(
            {
                round((len(history) - 1) * fraction)
                for fraction in (0, 0.25, 0.5, 0.75, 1)
            }
        )
        fig, ax = plt.subplots(figsize=(8, 5))
        for index in indices:
            snapshot = history[index]
            objectives = snapshot.get("objectives", [])
            if objectives:
                points = [vector for vector in objectives if vector[2] == 0]
            else:
                points = snapshot.get("front", [])
                if violation_policy:
                    points = [vector for vector in points if vector[2] == 0]
                else:
                    points = [
                        vector
                        for vector in points
                        if chosen == "infinity" or vector[2] <= chosen + 1e-8
                    ]
            points.sort(key=lambda v: v[1])
            if points:
                label = f"iteration {snapshot.get('iteration', index)}"
                ax.plot(
                    [v[1] for v in points],
                    [-v[0] for v in points],
                    marker=".",
                    label=label,
                    alpha=0.8,
                )
        ax.set(
            xlabel="Mean completion time (s; minimize)",
            ylabel="Team reward (maximize)",
            title=f"Pareto-front evolution at Tc={chosen} s",
        )
        ax.grid(alpha=0.2)
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(output / "pareto-evolution.png", dpi=150)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    scatter = ax.scatter(
        [s["peak_staleness"] for s in front],
        [s["reward"] for s in front],
        c=[s["objectives"][1] for s in front],
        cmap="viridis",
    )
    for row in slices:
        if row["tc"] != "infinity":
            ax.axvline(row["tc"], color="grey", alpha=0.15)
    fig.colorbar(scatter, ax=ax, label="Mean completion time (s)")
    ax.set(
        xlabel="Peak staleness Δ (s; minimize)",
        ylabel="Team reward (maximize)",
        title="Reward–staleness view of violation archive"
        if violation_policy
        else "Three-objective archive",
    )
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output / "delta-tradeoff.png", dpi=150)
    plt.close(fig)
