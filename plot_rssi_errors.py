#!/usr/bin/env python3
"""
Create scatterplot of RSSI errors combining:
1. M2_N100 to M50_N100 results
2. Benchmark results from p*.* problem instances
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pickle
from pathlib import Path

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
        print(f"Error reading {scores_file}: {e}")
        return None

    return np.array(scores) if len(scores) > 0 else None

def get_benchmark_rssi_data():
    """Extract RSSI data from benchmark problem instances."""
    benchmark_data = []

    # Find all p*.* directories in out/
    out_dir = Path("out")
    problem_dirs = sorted([d for d in out_dir.glob("p*.*") if d.is_dir()])

    for prob_dir in problem_dirs:
        instance_name = prob_dir.name

        # Load surrogate and exact scores
        surrogate_dir = prob_dir / "1.0" / "surrogate"
        exact_dir = prob_dir / "1.0" / "exact"

        surrogate_scores = load_scores_from_pickle(surrogate_dir)
        exact_scores = load_scores_from_pickle(exact_dir)

        if surrogate_scores is not None and exact_scores is not None:
            # Get mean RSSI values
            surrogate_rssi = np.mean(surrogate_scores[:, 1])
            exact_rssi = np.mean(exact_scores[:, 1])
            rssi_error = exact_rssi - surrogate_rssi  # Positive = exact is better

            # Get best scores
            best_surrogate_rssi = surrogate_scores[np.argmax(surrogate_scores[:, 0]), 1]
            best_exact_rssi = exact_scores[np.argmax(exact_scores[:, 0]), 1]
            best_rssi_error = best_exact_rssi - best_surrogate_rssi

            benchmark_data.append({
                'instance': instance_name,
                'dataset': 'Chao Benchmark',
                'surrogate_rssi_mean': surrogate_rssi,
                'exact_rssi_mean': exact_rssi,
                'rssi_error_mean': rssi_error,
                'rssi_error_percent': (rssi_error / exact_rssi) * 100,
                'surrogate_rssi_best': best_surrogate_rssi,
                'exact_rssi_best': best_exact_rssi,
                'rssi_error_best': best_rssi_error,
                'num_surrogate_solutions': len(surrogate_scores),
                'num_exact_solutions': len(exact_scores)
            })

    return pd.DataFrame(benchmark_data)

def get_n100_rssi_data():
    """Extract RSSI data from M*_N100 results."""
    df = pd.read_csv('timing_results_mainpy/results.csv')

    # Filter for successful runs with both methods
    n100_data = []

    for instance in df['instance'].unique():
        instance_df = df[df['instance'] == instance]

        surrogate_row = instance_df[instance_df['method'] == 'surrogate']
        exact_row = instance_df[instance_df['method'] == 'exact']

        if len(surrogate_row) > 0 and len(exact_row) > 0:
            if surrogate_row['success'].values[0] and exact_row['success'].values[0]:
                map_name = instance.replace('.txt', '')

                # Load all scores for distribution analysis
                surrogate_scores = load_scores_from_pickle(Path("out") / map_name / "1.0" / "surrogate")
                exact_scores = load_scores_from_pickle(Path("out") / map_name / "1.0" / "exact")

                surrogate_rssi = surrogate_row['mean_rssi'].values[0]
                exact_rssi = exact_row['mean_rssi'].values[0]
                rssi_error = exact_rssi - surrogate_rssi

                # Get best RSSI from each method
                best_surrogate_rssi = surrogate_rssi
                best_exact_rssi = exact_rssi
                if surrogate_scores is not None and exact_scores is not None:
                    best_surrogate_rssi = surrogate_scores[np.argmax(surrogate_scores[:, 0]), 1]
                    best_exact_rssi = exact_scores[np.argmax(exact_scores[:, 0]), 1]

                best_rssi_error = best_exact_rssi - best_surrogate_rssi

                n100_data.append({
                    'instance': map_name,
                    'dataset': 'N=100 Timing',
                    'num_agents': surrogate_row['num_agents'].values[0],
                    'surrogate_rssi_mean': surrogate_rssi,
                    'exact_rssi_mean': exact_rssi,
                    'rssi_error_mean': rssi_error,
                    'rssi_error_percent': (rssi_error / exact_rssi) * 100,
                    'surrogate_rssi_best': best_surrogate_rssi,
                    'exact_rssi_best': best_exact_rssi,
                    'rssi_error_best': best_rssi_error,
                    'num_surrogate_solutions': surrogate_row['num_solutions'].values[0] if 'num_solutions' in surrogate_row else 1,
                    'num_exact_solutions': exact_row['num_solutions'].values[0] if 'num_solutions' in exact_row else 1
                })

    return pd.DataFrame(n100_data)

def create_rssi_error_scatterplot(n100_df, benchmark_df):
    """Create comprehensive RSSI error scatterplot."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # Plot 1: Mean RSSI Error Scatterplot
    ax1 = axes[0, 0]

    # N100 data
    if len(n100_df) > 0:
        scatter1 = ax1.scatter(n100_df['exact_rssi_mean'], n100_df['rssi_error_mean'],
                              s=100, alpha=0.7, c='#3498db', marker='o',
                              edgecolors='black', linewidths=1.5, label='N=100 Timing')

    # Benchmark data
    if len(benchmark_df) > 0:
        scatter2 = ax1.scatter(benchmark_df['exact_rssi_mean'], benchmark_df['rssi_error_mean'],
                              s=100, alpha=0.7, c='#e74c3c', marker='s',
                              edgecolors='black', linewidths=1.5, label='Chao Benchmark')

    ax1.axhline(0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
    ax1.set_xlabel('Exact Method Mean RSSI [dBm]', fontweight='bold', fontsize=11)
    ax1.set_ylabel('RSSI Error (Exact - Surrogate) [dBm]', fontweight='bold', fontsize=11)
    ax1.set_title('RSSI Error vs Exact RSSI (Mean Values)', fontweight='bold', fontsize=12)
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)

    # Plot 2: RSSI Error Distribution
    ax2 = axes[0, 1]

    all_errors = []
    labels = []
    colors = []

    if len(n100_df) > 0:
        all_errors.append(n100_df['rssi_error_mean'].values)
        labels.append('N=100 Timing')
        colors.append('#3498db')

    if len(benchmark_df) > 0:
        all_errors.append(benchmark_df['rssi_error_mean'].values)
        labels.append('Chao Benchmark')
        colors.append('#e74c3c')

    if len(all_errors) > 0:
        bp = ax2.boxplot(all_errors, labels=labels, patch_artist=True,
                         widths=0.6, showfliers=True)

        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        for whisker in bp['whiskers']:
            whisker.set(linewidth=1.5)
        for cap in bp['caps']:
            cap.set(linewidth=1.5)
        for median in bp['medians']:
            median.set(color='red', linewidth=2)

    ax2.axhline(0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
    ax2.set_ylabel('RSSI Error (Exact - Surrogate) [dBm]', fontweight='bold', fontsize=11)
    ax2.set_title('RSSI Error Distribution by Dataset', fontweight='bold', fontsize=12)
    ax2.grid(True, alpha=0.3, axis='y')

    # Plot 3: Percentage Error vs Problem Size
    ax3 = axes[1, 0]

    if len(n100_df) > 0 and 'num_agents' in n100_df.columns:
        ax3.scatter(n100_df['num_agents'], abs(n100_df['rssi_error_percent']),
                   s=120, alpha=0.7, c='#3498db', marker='o',
                   edgecolors='black', linewidths=1.5, label='N=100 Timing')

        # Add trend line
        z = np.polyfit(n100_df['num_agents'], abs(n100_df['rssi_error_percent']), 1)
        p = np.poly1d(z)
        x_trend = np.linspace(n100_df['num_agents'].min(), n100_df['num_agents'].max(), 100)
        ax3.plot(x_trend, p(x_trend), "b--", alpha=0.8, linewidth=2)

    ax3.set_xlabel('Number of Agents', fontweight='bold', fontsize=11)
    ax3.set_ylabel('Absolute RSSI Error (%)', fontweight='bold', fontsize=11)
    ax3.set_title('RSSI Error vs Problem Size', fontweight='bold', fontsize=12)
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3)

    # Plot 4: Best Solution RSSI Error
    ax4 = axes[1, 1]

    if len(n100_df) > 0:
        ax4.scatter(n100_df['exact_rssi_best'], n100_df['rssi_error_best'],
                   s=100, alpha=0.7, c='#3498db', marker='o',
                   edgecolors='black', linewidths=1.5, label='N=100 Timing')

    if len(benchmark_df) > 0:
        ax4.scatter(benchmark_df['exact_rssi_best'], benchmark_df['rssi_error_best'],
                   s=100, alpha=0.7, c='#e74c3c', marker='s',
                   edgecolors='black', linewidths=1.5, label='Chao Benchmark')

    ax4.axhline(0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
    ax4.set_xlabel('Exact Method Best RSSI [dBm]', fontweight='bold', fontsize=11)
    ax4.set_ylabel('RSSI Error (Exact - Surrogate) [dBm]', fontweight='bold', fontsize=11)
    ax4.set_title('RSSI Error for Best Solutions', fontweight='bold', fontsize=12)
    ax4.legend(fontsize=10)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('benchmark_results_mainpy/rssi_error_scatterplot.png', dpi=300, bbox_inches='tight')
    print("Saved: benchmark_results_mainpy/rssi_error_scatterplot.png")

def print_statistics(n100_df, benchmark_df):
    """Print summary statistics."""
    print("\n" + "="*70)
    print("RSSI ERROR STATISTICS")
    print("="*70)

    if len(n100_df) > 0:
        print("\nN=100 Timing Dataset:")
        print(f"  Instances: {len(n100_df)}")
        print(f"  Mean RSSI error: {n100_df['rssi_error_mean'].mean():.3f} ± {n100_df['rssi_error_mean'].std():.3f} dBm")
        print(f"  Mean RSSI error (%): {n100_df['rssi_error_percent'].mean():.2f}% ± {n100_df['rssi_error_percent'].std():.2f}%")
        print(f"  Range: [{n100_df['rssi_error_mean'].min():.3f}, {n100_df['rssi_error_mean'].max():.3f}] dBm")
        print(f"  Best solution RSSI error: {n100_df['rssi_error_best'].mean():.3f} ± {n100_df['rssi_error_best'].std():.3f} dBm")

    if len(benchmark_df) > 0:
        print("\nChao Benchmark Dataset:")
        print(f"  Instances: {len(benchmark_df)}")
        print(f"  Mean RSSI error: {benchmark_df['rssi_error_mean'].mean():.3f} ± {benchmark_df['rssi_error_mean'].std():.3f} dBm")
        print(f"  Mean RSSI error (%): {benchmark_df['rssi_error_percent'].mean():.2f}% ± {benchmark_df['rssi_error_percent'].std():.2f}%")
        print(f"  Range: [{benchmark_df['rssi_error_mean'].min():.3f}, {benchmark_df['rssi_error_mean'].max():.3f}] dBm")
        print(f"  Best solution RSSI error: {benchmark_df['rssi_error_best'].mean():.3f} ± {benchmark_df['rssi_error_best'].std():.3f} dBm")

    # Combined statistics
    all_errors = []
    all_percent = []

    if len(n100_df) > 0:
        all_errors.extend(n100_df['rssi_error_mean'].values)
        all_percent.extend(n100_df['rssi_error_percent'].values)

    if len(benchmark_df) > 0:
        all_errors.extend(benchmark_df['rssi_error_mean'].values)
        all_percent.extend(benchmark_df['rssi_error_percent'].values)

    if len(all_errors) > 0:
        all_errors = np.array(all_errors)
        all_percent = np.array(all_percent)

        print("\nCombined Statistics (All Instances):")
        print(f"  Total instances: {len(all_errors)}")
        print(f"  Mean RSSI error: {all_errors.mean():.3f} ± {all_errors.std():.3f} dBm")
        print(f"  Median RSSI error: {np.median(all_errors):.3f} dBm")
        print(f"  Mean RSSI error (%): {all_percent.mean():.2f}% ± {all_percent.std():.2f}%")
        print(f"  Range: [{all_errors.min():.3f}, {all_errors.max():.3f}] dBm")

        # Percentage within thresholds
        within_1_percent = np.sum(np.abs(all_percent) < 1) / len(all_percent) * 100
        within_2_percent = np.sum(np.abs(all_percent) < 2) / len(all_percent) * 100
        within_3_percent = np.sum(np.abs(all_percent) < 3) / len(all_percent) * 100

        print(f"\n  Instances with <1% RSSI error: {within_1_percent:.1f}%")
        print(f"  Instances with <2% RSSI error: {within_2_percent:.1f}%")
        print(f"  Instances with <3% RSSI error: {within_3_percent:.1f}%")

    print("="*70)

if __name__ == "__main__":
    print("Loading RSSI error data...")

    # Load N100 data
    n100_df = get_n100_rssi_data()
    print(f"Loaded {len(n100_df)} N=100 instances")

    # Load benchmark data
    benchmark_df = get_benchmark_rssi_data()
    print(f"Loaded {len(benchmark_df)} benchmark instances")

    # Create visualizations
    create_rssi_error_scatterplot(n100_df, benchmark_df)

    # Print statistics
    print_statistics(n100_df, benchmark_df)

    print("\nDone!")
