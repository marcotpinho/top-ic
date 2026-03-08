#!/usr/bin/env python3
"""
Create scatterplot showing surrogate RSSI vs exact RSSI
to visualize the correlation between the two methods.
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
                'dataset': 'Chao Benchmark',
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
                    'dataset': 'N=100 Timing',
                    'num_agents': surrogate_row['num_agents'].values[0],
                    'surrogate_rssi': surrogate_row['mean_rssi'].values[0],
                    'exact_rssi': exact_row['mean_rssi'].values[0],
                    'rssi_error': exact_row['mean_rssi'].values[0] - surrogate_row['mean_rssi'].values[0]
                })

    return pd.DataFrame(n100_data)

def create_surrogate_vs_exact_scatterplot(n100_df, benchmark_df):
    """Create scatterplot of surrogate RSSI vs exact RSSI."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Plot 1: Surrogate vs Exact RSSI (both datasets)
    ax1 = axes[0]

    # Combine all data for ideal line
    all_rssi = []

    if len(n100_df) > 0:
        scatter1 = ax1.scatter(n100_df['surrogate_rssi'], n100_df['exact_rssi'],
                              s=150, alpha=0.7, c='#3498db', marker='o',
                              edgecolors='black', linewidths=2, label='N=100 Timing',
                              zorder=3)
        all_rssi.extend(list(n100_df['surrogate_rssi'].values) + list(n100_df['exact_rssi'].values))

    if len(benchmark_df) > 0:
        scatter2 = ax1.scatter(benchmark_df['surrogate_rssi'], benchmark_df['exact_rssi'],
                              s=120, alpha=0.6, c='#e74c3c', marker='s',
                              edgecolors='black', linewidths=1.5, label='Chao Benchmark',
                              zorder=2)
        all_rssi.extend(list(benchmark_df['surrogate_rssi'].values) + list(benchmark_df['exact_rssi'].values))

    # Calculate and plot ideal line (y=x)
    if len(all_rssi) > 0:
        min_rssi = min(all_rssi)
        max_rssi = max(all_rssi)
        margin = (max_rssi - min_rssi) * 0.05
        ideal_line = np.linspace(min_rssi - margin, max_rssi + margin, 100)
        ax1.plot(ideal_line, ideal_line, 'k--', linewidth=2, alpha=0.5,
                label='Perfect agreement (y=x)', zorder=1)

    # Calculate and plot regression line for all data
    if len(n100_df) > 0 or len(benchmark_df) > 0:
        all_surrogate = []
        all_exact = []

        if len(n100_df) > 0:
            all_surrogate.extend(n100_df['surrogate_rssi'].values)
            all_exact.extend(n100_df['exact_rssi'].values)

        if len(benchmark_df) > 0:
            all_surrogate.extend(benchmark_df['surrogate_rssi'].values)
            all_exact.extend(benchmark_df['exact_rssi'].values)

        all_surrogate = np.array(all_surrogate)
        all_exact = np.array(all_exact)

        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(all_surrogate, all_exact)
        regression_line = slope * ideal_line + intercept
        ax1.plot(ideal_line, regression_line, 'r-', linewidth=2, alpha=0.7,
                label=f'Linear fit (R²={r_value**2:.3f})', zorder=1)

        # Add regression equation and statistics
        textstr = f'y = {slope:.3f}x + {intercept:.3f}\nR² = {r_value**2:.3f}\np < {p_value:.2e}'
        ax1.text(0.05, 0.95, textstr, transform=ax1.transAxes,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    ax1.set_xlabel('Surrogate Method RSSI [dBm]', fontweight='bold', fontsize=12)
    ax1.set_ylabel('Exact Method RSSI [dBm]', fontweight='bold', fontsize=12)
    ax1.set_title('Surrogate vs Exact RSSI: All Instances', fontweight='bold', fontsize=13)
    ax1.legend(fontsize=10, loc='lower right')
    ax1.grid(True, alpha=0.3)
    ax1.set_aspect('equal', adjustable='box')

    # Plot 2: Separate plots for each dataset with residuals
    ax2 = axes[1]

    # Calculate residuals for both datasets
    if len(n100_df) > 0:
        n100_residuals = n100_df['exact_rssi'] - n100_df['surrogate_rssi']
        ax2.scatter(n100_df['surrogate_rssi'], n100_residuals,
                   s=150, alpha=0.7, c='#3498db', marker='o',
                   edgecolors='black', linewidths=2, label='N=100 Timing')

    if len(benchmark_df) > 0:
        benchmark_residuals = benchmark_df['exact_rssi'] - benchmark_df['surrogate_rssi']
        ax2.scatter(benchmark_df['surrogate_rssi'], benchmark_residuals,
                   s=120, alpha=0.6, c='#e74c3c', marker='s',
                   edgecolors='black', linewidths=1.5, label='Chao Benchmark')

    # Zero line
    ax2.axhline(0, color='black', linestyle='--', linewidth=2, alpha=0.5)

    # Add mean residual lines
    if len(n100_df) > 0:
        ax2.axhline(n100_residuals.mean(), color='#3498db', linestyle='-',
                   linewidth=2, alpha=0.5, label=f'N=100 mean: {n100_residuals.mean():.2f} dBm')

    if len(benchmark_df) > 0:
        ax2.axhline(benchmark_residuals.mean(), color='#e74c3c', linestyle='-',
                   linewidth=2, alpha=0.5, label=f'Chao mean: {benchmark_residuals.mean():.2f} dBm')

    ax2.set_xlabel('Surrogate Method RSSI [dBm]', fontweight='bold', fontsize=12)
    ax2.set_ylabel('Residual (Exact - Surrogate) [dBm]', fontweight='bold', fontsize=12)
    ax2.set_title('Residual Analysis', fontweight='bold', fontsize=13)
    ax2.legend(fontsize=9, loc='best')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('benchmark_results_mainpy/surrogate_vs_exact_rssi.png', dpi=300, bbox_inches='tight')
    print("Saved: benchmark_results_mainpy/surrogate_vs_exact_rssi.png")

def print_correlation_stats(n100_df, benchmark_df):
    """Print correlation statistics."""
    print("\n" + "="*70)
    print("CORRELATION ANALYSIS: Surrogate vs Exact RSSI")
    print("="*70)

    if len(n100_df) > 0:
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            n100_df['surrogate_rssi'], n100_df['exact_rssi'])

        print("\nN=100 Timing Dataset:")
        print(f"  Instances: {len(n100_df)}")
        print(f"  Pearson correlation: {r_value:.4f}")
        print(f"  R²: {r_value**2:.4f}")
        print(f"  Linear fit: y = {slope:.4f}x + {intercept:.4f}")
        print(f"  p-value: {p_value:.2e}")
        print(f"  Mean absolute error: {np.abs(n100_df['rssi_error']).mean():.3f} dBm")
        print(f"  RMSE: {np.sqrt(np.mean(n100_df['rssi_error']**2)):.3f} dBm")

    if len(benchmark_df) > 0:
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            benchmark_df['surrogate_rssi'], benchmark_df['exact_rssi'])

        print("\nChao Benchmark Dataset:")
        print(f"  Instances: {len(benchmark_df)}")
        print(f"  Pearson correlation: {r_value:.4f}")
        print(f"  R²: {r_value**2:.4f}")
        print(f"  Linear fit: y = {slope:.4f}x + {intercept:.4f}")
        print(f"  p-value: {p_value:.2e}")
        print(f"  Mean absolute error: {np.abs(benchmark_df['rssi_error']).mean():.3f} dBm")
        print(f"  RMSE: {np.sqrt(np.mean(benchmark_df['rssi_error']**2)):.3f} dBm")

    # Combined correlation
    if len(n100_df) > 0 or len(benchmark_df) > 0:
        all_surrogate = []
        all_exact = []

        if len(n100_df) > 0:
            all_surrogate.extend(n100_df['surrogate_rssi'].values)
            all_exact.extend(n100_df['exact_rssi'].values)

        if len(benchmark_df) > 0:
            all_surrogate.extend(benchmark_df['surrogate_rssi'].values)
            all_exact.extend(benchmark_df['exact_rssi'].values)

        all_surrogate = np.array(all_surrogate)
        all_exact = np.array(all_exact)

        slope, intercept, r_value, p_value, std_err = stats.linregress(all_surrogate, all_exact)

        print("\nCombined Dataset:")
        print(f"  Total instances: {len(all_surrogate)}")
        print(f"  Pearson correlation: {r_value:.4f}")
        print(f"  R²: {r_value**2:.4f}")
        print(f"  Linear fit: y = {slope:.4f}x + {intercept:.4f}")
        print(f"  p-value: {p_value:.2e}")

        errors = all_exact - all_surrogate
        print(f"  Mean absolute error: {np.abs(errors).mean():.3f} dBm")
        print(f"  RMSE: {np.sqrt(np.mean(errors**2)):.3f} dBm")

        # Percentage of variance explained
        print(f"\n  Variance explained: {r_value**2 * 100:.1f}%")

        # How close to perfect agreement (y=x)
        perfect_slope_diff = abs(1.0 - slope)
        print(f"  Deviation from perfect slope (1.0): {perfect_slope_diff:.4f}")
        print(f"  Intercept deviation from zero: {abs(intercept):.4f} dBm")

    print("="*70)

if __name__ == "__main__":
    print("Loading RSSI data...")

    # Load data
    n100_df = get_n100_rssi_data()
    print(f"Loaded {len(n100_df)} N=100 instances")

    benchmark_df = get_benchmark_rssi_data()
    print(f"Loaded {len(benchmark_df)} benchmark instances")

    # Create visualization
    create_surrogate_vs_exact_scatterplot(n100_df, benchmark_df)

    # Print statistics
    print_correlation_stats(n100_df, benchmark_df)

    print("\nDone!")
