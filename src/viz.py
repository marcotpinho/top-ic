"""Visualization utilities for TOP-CC solutions.

This module is only imported when --plot is used. It has no imports from
the core solver loop — it takes positions, paths, and scores as data.
"""

import os
import numpy as np
from matplotlib import pyplot as plt


def translate_path_to_coordinates(paths, positions):
    return [positions[reward] for reward in paths]


def get_path_length(path):
    return np.sum(np.linalg.norm(np.diff(path, axis=0), axis=1))


def plot_rewards(ax, reward_p, reward_value, not_plot=set()):
    rewards_1 = [i for i in range(len(reward_p) - 2) if i not in not_plot]
    scatter = ax.scatter(
        reward_p[rewards_1, 0], reward_p[rewards_1, 1],
        c=reward_value[rewards_1], cmap="viridis", edgecolors="black",
        s=700, label="PoI", marker="D", vmin=1, vmax=10,
    )
    ax.scatter(reward_p[-1, 0], reward_p[-1, 1], c="#ff6361", edgecolors="black", s=800, label="Start", marker="s")
    ax.scatter(reward_p[-2, 0], reward_p[-2, 1], c="#58508d", edgecolors="black", s=800, label="Goal", marker="X")
    rewards_2 = [i for i in range(len(reward_p)) if i in not_plot]
    ax.scatter(reward_p[rewards_2, 0], reward_p[rewards_2, 1], c="#58508d", edgecolors="black", label="Visited PoI", s=700, marker="o")
    return scatter


def plot_path(ax, path, show_path=True, color="orange", show_arrow=True):
    prev = path[0]
    for curr in path[1:]:
        if show_path:
            ax.plot([prev[0], curr[0]], [prev[1], curr[1]], linewidth=5, color=color)
        dx, dy = curr[0] - prev[0], curr[1] - prev[1]
        norm = np.sqrt(dx**2 + dy**2)
        if norm > 0 and show_arrow:
            dx_fixed = (dx / norm) * 0.5
            dy_fixed = (dy / norm) * 0.5
            ax.quiver(
                prev[0], prev[1], dx_fixed, dy_fixed,
                angles="xy", scale_units="xy", scale=1, color=color,
                width=0.01, headlength=20, headwidth=20, headaxislength=19,
            )
        prev = curr
    plot_max_distance(ax, [path])


def plot_max_distance(ax, individual):
    max_size = max(len(ind) for ind in individual)
    individual = [
        np.vstack([ind, np.tile(ind[-1], (max_size - len(ind), 1))])
        for ind in individual
    ]
    max_distance = 0
    point1 = point2 = None
    for i in range(len(individual)):
        for j in range(i + 1, len(individual)):
            distances = np.linalg.norm(individual[i] - individual[j], axis=1)
            max_dist_index = np.argmax(distances)
            if distances[max_dist_index] > max_distance:
                max_distance = distances[max_dist_index]
                point1 = individual[i][max_dist_index]
                point2 = individual[j][max_dist_index]
    if point1 is not None and point2 is not None:
        ax.plot([point1[0], point2[0]], [point1[1], point2[1]], "r--", label="Max Distance", linewidth=3)
        ax.scatter(point1[0], point1[1], c="r", marker="o")
        ax.scatter(point2[0], point2[1], c="r", marker="o")


def plot_paths_with_rewards(rpositions, rvalues, individual, scores, directory=None, fname=None):
    n_agents = len(individual)
    colormap = plt.cm.get_cmap("tab10", n_agents)
    colors = [colormap(i) for i in range(n_agents)]

    fig, ax = plt.subplots(figsize=(20, 20))
    fig.patch.set_facecolor("grey")
    ax.set_facecolor("grey")
    plot_rewards(ax, rpositions, rvalues)

    individual = translate_path_to_coordinates(individual, rpositions)
    length = [get_path_length(ind) for ind in individual]

    for i in range(n_agents):
        plot_path(ax, individual[i], color=colors[i])

    ax.set_title(
        "Individual Paths - score: "
        + str([float(score) for score in scores])
        + " - length: "
        + str([float(l) for l in length])
    )
    plt.grid(True)
    plt.axis("equal")
    plt.ylim(0, None)
    plt.xlim(0, None)

    if directory:
        os.makedirs(directory, exist_ok=True)
        plt.savefig(f"{directory}/{fname if fname else 'paths'}.png")
    plt.close()
