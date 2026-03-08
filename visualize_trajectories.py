#!/usr/bin/env python3
"""
Visualize trajectory comparisons between exact and surrogate methods.
Shows typical case and worst case for RSSI degradation.
"""
import numpy as np
import matplotlib.pyplot as plt
import pickle
from pathlib import Path

def load_map(map_file):
    """Load map data."""
    with open(map_file, 'r') as f:
        lines = f.readlines()

    # Parse header
    n_waypoints = int(lines[0].split()[1])
    n_agents = int(lines[1].split()[1])
    # Skip tmax line if present
    start_line = 3 if lines[2].startswith('tmax') else 2

    # Parse waypoints (they have x, y, and a third value - likely importance/weight)
    waypoints = []
    for i in range(start_line, start_line + n_waypoints):
        parts = lines[i].strip().split()
        x, y = float(parts[0]), float(parts[1])
        waypoints.append([x, y])

    # Parse agent starts (assuming they follow waypoints)
    # In this format, agents are specified at the end
    # Let's just take the last n_agents waypoints as agent starts
    # Actually, all entries are waypoints. Let me check if there's a different format
    # For now, let's assume agent starts are distributed among waypoints
    # We'll use the first n_agents waypoints as agent starting positions
    agent_starts = waypoints[:n_agents] if len(waypoints) >= n_agents else waypoints

    return np.array(waypoints), np.array(agent_starts), n_agents, n_waypoints

def load_best_path(map_name, method, out_dir="out", speed="1.0"):
    """Load the best trajectory path."""
    results_dir = Path(out_dir) / map_name / speed / method
    paths_file = results_dir / "paths.pkl"
    scores_file = results_dir / "scores.pkl"

    if not paths_file.exists() or not scores_file.exists():
        return None, None

    # Load all paths and scores
    paths = []
    scores = []

    try:
        with open(paths_file, 'rb') as f:
            while True:
                try:
                    path = pickle.load(f)
                    paths.append(path)
                except EOFError:
                    break

        with open(scores_file, 'rb') as f:
            while True:
                try:
                    score = pickle.load(f)
                    scores.append(score)
                except EOFError:
                    break
    except Exception as e:
        print(f"Error loading paths/scores: {e}")
        return None, None

    if len(paths) == 0 or len(scores) == 0:
        return None, None

    # Find best path (highest reward)
    scores = np.array(scores)
    best_idx = np.argmax(scores[:, 0])  # Maximize reward

    return paths[best_idx], scores[best_idx]

def visualize_trajectory_comparison(map_name, case_name):
    """Visualize trajectory comparison for a specific map."""
    # Load map
    map_file = f"maps/timing_experiments/{map_name}.txt"
    waypoints, agent_starts, n_agents, n_waypoints = load_map(map_file)

    # Load paths
    surrogate_path, surrogate_score = load_best_path(map_name, 'surrogate')
    exact_path, exact_score = load_best_path(map_name, 'exact')

    if surrogate_path is None or exact_path is None:
        print(f"Could not load paths for {map_name}")
        return

    # Create visualization
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    for idx, (ax, path, score, method) in enumerate([
        (axes[0], surrogate_path, surrogate_score, 'Surrogate'),
        (axes[1], exact_path, exact_score, 'Exact')
    ]):
        # Plot waypoints
        ax.scatter(waypoints[:, 0], waypoints[:, 1], c='gold', s=150,
                  marker='*', edgecolors='black', linewidths=1.5,
                  label=f'Waypoints (n={n_waypoints})', zorder=5)

        # Plot agent starting positions
        ax.scatter(agent_starts[:, 0], agent_starts[:, 1], c='blue', s=100,
                  marker='s', edgecolors='black', linewidths=1.5,
                  label=f'Agent Starts (n={n_agents})', zorder=5)

        # Plot paths for each agent
        # Paths are stored as indices into waypoints array
        # -1 = start, -2 = end, other values are waypoint indices
        colors = plt.cm.tab20(np.linspace(0, 1, n_agents))

        for agent_id in range(n_agents):
            agent_path_indices = path[agent_id]
            if len(agent_path_indices) > 0:
                # Convert indices to coordinates
                coords = []
                for idx in agent_path_indices:
                    if idx == -1:
                        # Start position
                        coords.append(agent_starts[agent_id])
                    elif idx == -2:
                        # End position (same as start)
                        coords.append(agent_starts[agent_id])
                    else:
                        # Waypoint
                        coords.append(waypoints[idx])

                if len(coords) > 1:
                    coords = np.array(coords)
                    ax.plot(coords[:, 0], coords[:, 1],
                           color=colors[agent_id], linewidth=2, alpha=0.7,
                           zorder=3)

                    # Mark path direction with arrows
                    mid_idx = len(coords) // 2
                    if mid_idx > 0:
                        dx = coords[mid_idx, 0] - coords[mid_idx-1, 0]
                        dy = coords[mid_idx, 1] - coords[mid_idx-1, 1]
                        if abs(dx) > 0.01 or abs(dy) > 0.01:  # Only draw arrow if there's movement
                            ax.arrow(coords[mid_idx-1, 0], coords[mid_idx-1, 1],
                                    dx * 0.3, dy * 0.3,
                                    head_width=3, head_length=2, fc=colors[agent_id],
                                    ec=colors[agent_id], alpha=0.6, zorder=4)

        # Formatting
        reward, rssi = score[0], score[1]
        ax.set_title(f'{method} Method\nReward: {reward:.0f}, RSSI: {rssi:.2f} dBm',
                    fontweight='bold', fontsize=12)
        ax.set_xlabel('X coordinate', fontweight='bold')
        ax.set_ylabel('Y coordinate', fontweight='bold')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal', adjustable='box')

    # Add overall title
    rssi_gap = exact_score[1] - surrogate_score[1]
    fig.suptitle(f'{case_name}: {map_name}\nRSSI Gap: {rssi_gap:.2f} dBm ({abs(rssi_gap/exact_score[1]*100):.2f}%)',
                fontweight='bold', fontsize=14, y=1.00)

    plt.tight_layout()
    plt.savefig(f'benchmark_results_mainpy/trajectory_{map_name}_{case_name.lower().replace(" ", "_")}.png',
                dpi=300, bbox_inches='tight')
    print(f"Saved: benchmark_results_mainpy/trajectory_{map_name}_{case_name.lower().replace(' ', '_')}.png")

    plt.close()

def create_rssi_distribution_comparison(map_name, case_name):
    """Compare RSSI distributions between exact and surrogate."""
    # Load all scores
    surrogate_scores = []
    exact_scores = []

    surrogate_dir = Path("out") / map_name / "1.0" / "surrogate"
    exact_dir = Path("out") / map_name / "1.0" / "exact"

    # Load surrogate scores
    if (surrogate_dir / "scores.pkl").exists():
        with open(surrogate_dir / "scores.pkl", 'rb') as f:
            while True:
                try:
                    score = pickle.load(f)
                    surrogate_scores.append(score)
                except EOFError:
                    break

    # Load exact scores
    if (exact_dir / "scores.pkl").exists():
        with open(exact_dir / "scores.pkl", 'rb') as f:
            while True:
                try:
                    score = pickle.load(f)
                    exact_scores.append(score)
                except EOFError:
                    break

    if len(surrogate_scores) == 0 or len(exact_scores) == 0:
        print(f"No scores found for {map_name}")
        return

    surrogate_scores = np.array(surrogate_scores)
    exact_scores = np.array(exact_scores)

    # Create distribution plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # RSSI distribution
    ax1 = axes[0]
    ax1.hist(surrogate_scores[:, 1], bins=20, alpha=0.6, label='Surrogate',
            color='#e74c3c', edgecolor='black')
    ax1.hist(exact_scores[:, 1], bins=20, alpha=0.6, label='Exact',
            color='#2ecc71', edgecolor='black')
    ax1.axvline(surrogate_scores[:, 1].mean(), color='#c0392b',
               linestyle='--', linewidth=2, label=f'Surrogate mean: {surrogate_scores[:, 1].mean():.2f}')
    ax1.axvline(exact_scores[:, 1].mean(), color='#27ae60',
               linestyle='--', linewidth=2, label=f'Exact mean: {exact_scores[:, 1].mean():.2f}')
    ax1.set_xlabel('RSSI [dBm]', fontweight='bold')
    ax1.set_ylabel('Frequency', fontweight='bold')
    ax1.set_title(f'RSSI Distribution\n{map_name}', fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Reward distribution
    ax2 = axes[1]
    ax2.hist(surrogate_scores[:, 0], bins=20, alpha=0.6, label='Surrogate',
            color='#e74c3c', edgecolor='black')
    ax2.hist(exact_scores[:, 0], bins=20, alpha=0.6, label='Exact',
            color='#2ecc71', edgecolor='black')
    ax2.axvline(surrogate_scores[:, 0].mean(), color='#c0392b',
               linestyle='--', linewidth=2)
    ax2.axvline(exact_scores[:, 0].mean(), color='#27ae60',
               linestyle='--', linewidth=2)
    ax2.set_xlabel('Reward', fontweight='bold')
    ax2.set_ylabel('Frequency', fontweight='bold')
    ax2.set_title(f'Reward Distribution\n{map_name}', fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.suptitle(f'{case_name}: Solution Quality Distributions', fontweight='bold', fontsize=14)
    plt.tight_layout()
    plt.savefig(f'benchmark_results_mainpy/distributions_{map_name}_{case_name.lower().replace(" ", "_")}.png',
                dpi=300, bbox_inches='tight')
    print(f"Saved: benchmark_results_mainpy/distributions_{map_name}_{case_name.lower().replace(' ', '_')}.png")

    plt.close()

    # Print statistics
    print(f"\n{case_name}: {map_name}")
    print(f"  Surrogate: {len(surrogate_scores)} solutions")
    print(f"    RSSI: {surrogate_scores[:, 1].mean():.2f} ± {surrogate_scores[:, 1].std():.2f} dBm")
    print(f"    Reward: {surrogate_scores[:, 0].mean():.2f} ± {surrogate_scores[:, 0].std():.2f}")
    print(f"  Exact: {len(exact_scores)} solutions")
    print(f"    RSSI: {exact_scores[:, 1].mean():.2f} ± {exact_scores[:, 1].std():.2f} dBm")
    print(f"    Reward: {exact_scores[:, 0].mean():.2f} ± {exact_scores[:, 0].std():.2f}")
    print(f"  RSSI gap: {exact_scores[:, 1].mean() - surrogate_scores[:, 1].mean():.2f} dBm")

if __name__ == "__main__":
    print("=" * 70)
    print("Trajectory Visualization: Typical and Worst Cases")
    print("=" * 70)

    # Cases identified from analysis
    cases = [
        ("M20_N100", "Best Case"),
        ("M30_N100", "Typical Case"),
        ("M10_N100", "Worst Case")
    ]

    for map_name, case_name in cases:
        print(f"\nProcessing {case_name}: {map_name}...")
        visualize_trajectory_comparison(map_name, case_name)
        create_rssi_distribution_comparison(map_name, case_name)

    print("\n" + "=" * 70)
    print("Trajectory visualization complete!")
    print("=" * 70)
