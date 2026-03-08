#!/usr/bin/env python3
"""
Create unified scatterplot showing surrogate RSSI vs exact RSSI
without distinguishing between datasets.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pickle
from pathlib import Path
from scipy import stats

def load_scores_from_pickle(results_dir):
    """Load all scores from a pickle file."""
    scores_file = results_dir / "scores.pkl"
    if not scores_file.exists():
        return None

    scores = []
    try:
        with open(scores_file, 'rb') as f:
            while True:
                try:
                    score = pickle.load(f)
                    scores.append(score)
                except EOFError:
                    break
    except Exception as e:
        return None

    return np.array(scores) if len(scores) > 0 else None

def get_benchmark_rssi_data():
    """Extract RSSI data from benchmark problem instances."""
    benchmark_data = []
    out_dir = Path("out")
    problem_dirs = sorted([d for d in out_dir.glob("p*.*") if d.is_dir()])

    for prob_dir in problem_dirs:
        instance_name = prob_dir.name
        surrogate_dir = prob_dir / "1.0" / "surrogate"
        exact_dir = prob_dir / "1.0" / "exact"

        surrogate_scores = load_scores_from_pickle(surrogate_dir)
        exact_scores = load_scores_from_pickle(exact_dir)

        if surrogate_scores is not None and exact_scores is not None:
            surrogate_rssi = np.mean(surrogate_scores[:, 1])
            exact_rssi = np.mean(exact_scores[:, 1])

            benchmark_data.append({
                'instance': instance_name,
                'surrogate_rssi': surrogate_rssi,
                'exact_rssi': exact_rssi,
                'rssi_error': exact_rssi - surrogate_rssi
            })

    return pd.DataFrame(benchmark_data)

def get_n100_rssi_data():
    """Extract RSSI data from M*_N100 results."""
    df = pd.read_csv('timing_results_mainpy/results.csv')
    n100_data = []

    for instance in df['instance'].unique():
        instance_df = df[df['instance'] == instance]
        surrogate_row = instance_df[instance_df['method'] == 'surrogate']
        exact_row = instance_df[instance_df['method'] == 'exact']

        if len(surrogate_row) > 0 and len(exact_row) > 0:
            if surrogate_row['success'].values[0] and exact_row['success'].values[0]:
                n100_data.append({
                    'instance': instance.replace('.txt', ''),
                    'num_agents': surrogate_row['num_agents'].values[0],
                    'surrogate_rssi': surrogate_row['mean_rssi'].values[0],
                    'exact_rssi': exact_row['mean_rssi'].values[0],
                    'rssi_error': exact_row['mean_rssi'].values[0] - surrogate_row['mean_rssi'].values[0]
                })

    return pd.DataFrame(n100_data)

def create_unified_scatterplot(all_data):
    """Create unified scatterplot of surrogate RSSI vs exact RSSI."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Extract data
    surrogate_rssi = all_data['surrogate_rssi'].values
    exact_rssi = all_data['exact_rssi'].values
    residuals = exact_rssi - surrogate_rssi

    # Plot 1: Surrogate vs Exact RSSI
    ax1 = axes[0]

    # Scatter plot - all points in same style
    scatter = ax1.scatter(surrogate_rssi, exact_rssi,
                         s=100, alpha=0.6, c='#2c3e50', marker='o',
                         edgecolors='black', linewidths=1.5, zorder=3)

    # Calculate and plot ideal line (y=x)
    min_rssi = min(surrogate_rssi.min(), exact_rssi.min())
    max_rssi = max(surrogate_rssi.max(), exact_rssi.max())
    margin = (max_rssi - min_rssi) * 0.05
    ideal_line = np.linspace(min_rssi - margin, max_rssi + margin, 100)
    ax1.plot(ideal_line, ideal_line, 'k--', linewidth=2.5, alpha=0.7,
            label='Perfect agreement (y=x)', zorder=1)

    # Calculate and plot regression line
    slope, intercept, r_value, p_value, std_err = stats.linregress(surrogate_rssi, exact_rssi)
    regression_line = slope * ideal_line + intercept
    ax1.plot(ideal_line, regression_line, 'r-', linewidth=2.5, alpha=0.8,
            label=f'Linear fit (R²={r_value**2:.3f})', zorder=2)

    # Add regression equation and statistics
    textstr = f'y = {slope:.3f}x + {intercept:.2f}\nR² = {r_value**2:.3f}\nn = {len(all_data)}'
    ax1.text(0.05, 0.95, textstr, transform=ax1.transAxes,
            fontsize=11, verticalalignment='top', fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9, edgecolor='black', linewidth=1.5))

    ax1.set_xlabel('Surrogate RSSI [dBm]', fontweight='bold', fontsize=13)
    ax1.set_ylabel('Exact RSSI [dBm]', fontweight='bold', fontsize=13)
    ax1.set_title('Surrogate vs Exact RSSI', fontweight='bold', fontsize=14)
    ax1.legend(fontsize=11, loc='lower right', framealpha=0.9)
    ax1.grid(True, alpha=0.3)
    ax1.set_aspect('equal', adjustable='box')

    # Plot 2: Residual Analysis
    ax2 = axes[1]

    # Scatter plot of residuals
    ax2.scatter(surrogate_rssi, residuals,
               s=100, alpha=0.6, c='#2c3e50', marker='o',
               edgecolors='black', linewidths=1.5)

    # Zero line
    ax2.axhline(0, color='black', linestyle='--', linewidth=2.5, alpha=0.7,
               label='Zero error')

    # Mean residual line
    mean_residual = residuals.mean()
    ax2.axhline(mean_residual, color='#e74c3c', linestyle='-',
               linewidth=2.5, alpha=0.8, label=f'Mean: {mean_residual:.2f} dBm')

    # Add ±1 std bands
    std_residual = residuals.std()
    ax2.axhline(mean_residual + std_residual, color='#e74c3c', linestyle=':',
               linewidth=2, alpha=0.6)
    ax2.axhline(mean_residual - std_residual, color='#e74c3c', linestyle=':',
               linewidth=2, alpha=0.6)
    ax2.fill_between([surrogate_rssi.min(), surrogate_rssi.max()],
                     mean_residual - std_residual, mean_residual + std_residual,
                     color='#e74c3c', alpha=0.1, label=f'±1σ ({std_residual:.2f} dBm)')

    # Add statistics text
    mae = np.abs(residuals).mean()
    rmse = np.sqrt(np.mean(residuals**2))
    textstr = f'MAE = {mae:.2f} dBm\nRMSE = {rmse:.2f} dBm\nStd = {std_residual:.2f} dBm'
    ax2.text(0.95, 0.95, textstr, transform=ax2.transAxes,
            fontsize=11, verticalalignment='top', horizontalalignment='right',
            fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.9, edgecolor='black', linewidth=1.5))

    ax2.set_xlabel('Surrogate RSSI [dBm]', fontweight='bold', fontsize=13)
    ax2.set_ylabel('Residual (Exact - Surrogate) [dBm]', fontweight='bold', fontsize=13)
    ax2.set_title('Residual Analysis', fontweight='bold', fontsize=14)
    ax2.legend(fontsize=11, loc='upper left', framealpha=0.9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('benchmark_results_mainpy/surrogate_vs_exact_rssi_unified.png', dpi=300, bbox_inches='tight')
    print("Saved: benchmark_results_mainpy/surrogate_vs_exact_rssi_unified.png")

def print_statistics(all_data):
    """Print comprehensive statistics."""
    surrogate_rssi = all_data['surrogate_rssi'].values
    exact_rssi = all_data['exact_rssi'].values
    residuals = exact_rssi - surrogate_rssi

    slope, intercept, r_value, p_value, std_err = stats.linregress(surrogate_rssi, exact_rssi)

    print("\n" + "="*70)
    print("UNIFIED RSSI CORRELATION ANALYSIS")
    print("="*70)
    print(f"\nTotal instances: {len(all_data)}")
    print(f"\nLinear Regression:")
    print(f"  Equation: y = {slope:.4f}x + {intercept:.4f}")
    print(f"  Pearson correlation (r): {r_value:.4f}")
    print(f"  R² (coefficient of determination): {r_value**2:.4f}")
    print(f"  p-value: {p_value:.2e}")
    print(f"  Standard error: {std_err:.4f}")

    print(f"\nError Metrics:")
    print(f"  Mean residual (bias): {residuals.mean():.3f} dBm")
    print(f"  Std of residuals: {residuals.std():.3f} dBm")
    print(f"  Mean absolute error (MAE): {np.abs(residuals).mean():.3f} dBm")
    print(f"  Root mean square error (RMSE): {np.sqrt(np.mean(residuals**2)):.3f} dBm")
    print(f"  Min residual: {residuals.min():.3f} dBm")
    print(f"  Max residual: {residuals.max():.3f} dBm")

    print(f"\nModel Quality:")
    print(f"  Variance explained: {r_value**2 * 100:.1f}%")
    print(f"  Deviation from perfect slope (1.0): {abs(1.0 - slope):.4f}")
    print(f"  Intercept deviation from zero: {abs(intercept):.4f} dBm")

    # Percentage within error thresholds
    within_1_dBm = np.sum(np.abs(residuals) < 1) / len(residuals) * 100
    within_2_dBm = np.sum(np.abs(residuals) < 2) / len(residuals) * 100
    within_3_dBm = np.sum(np.abs(residuals) < 3) / len(residuals) * 100
    within_5_dBm = np.sum(np.abs(residuals) < 5) / len(residuals) * 100

    print(f"\nError Distribution:")
    print(f"  Within ±1 dBm: {within_1_dBm:.1f}%")
    print(f"  Within ±2 dBm: {within_2_dBm:.1f}%")
    print(f"  Within ±3 dBm: {within_3_dBm:.1f}%")
    print(f"  Within ±5 dBm: {within_5_dBm:.1f}%")

    print("="*70)

if __name__ == "__main__":
    print("Loading RSSI data...")

    # Load both datasets
    n100_df = get_n100_rssi_data()
    print(f"Loaded {len(n100_df)} N=100 instances")

    benchmark_df = get_benchmark_rssi_data()
    print(f"Loaded {len(benchmark_df)} benchmark instances")

    # Combine datasets
    all_data = pd.concat([n100_df[['instance', 'surrogate_rssi', 'exact_rssi', 'rssi_error']],
                          benchmark_df[['instance', 'surrogate_rssi', 'exact_rssi', 'rssi_error']]],
                         ignore_index=True)

    print(f"Total instances: {len(all_data)}")

    # Create visualization
    create_unified_scatterplot(all_data)

    # Print statistics
    print_statistics(all_data)

    print("\nDone!")
