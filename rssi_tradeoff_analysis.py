#!/usr/bin/env python3
"""
Comprehensive RSSI quality tradeoff analysis for surrogate vs exact methods.
Addresses reviewer concerns about communication quality preservation.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pickle
from pathlib import Path

# Set style
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = '#f0f0f0'
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.alpha'] = 0.3

def load_all_scores(map_name, method, out_dir="out", speed="1.0"):
    """Load all scores from pickle file."""
    results_dir = Path(out_dir) / map_name / speed / method
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

def load_paths(map_name, method, out_dir="out", speed="1.0"):
    """Load trajectory paths from pickle file."""
    results_dir = Path(out_dir) / map_name / speed / method
    paths_file = results_dir / "paths.pkl"

    if not paths_file.exists():
        return None

    paths = []
    try:
        with open(paths_file, 'rb') as f:
            while True:
                try:
                    path = pickle.load(f)
                    paths.append(path)
                except EOFError:
                    break
    except Exception as e:
        print(f"Error reading {paths_file}: {e}")
        return None

    return paths if len(paths) > 0 else None

def analyze_rssi_gaps():
    """Analyze RSSI gap distribution between exact and surrogate methods."""
    # Read results
    df = pd.read_csv('timing_results_mainpy/results.csv')

    # Filter for successful runs only (both methods succeeded)
    maps_both_success = []
    for instance in df['instance'].unique():
        instance_df = df[df['instance'] == instance]
        surrogate_success = instance_df[instance_df['method'] == 'surrogate']['success'].values
        exact_success = instance_df[instance_df['method'] == 'exact']['success'].values

        if len(surrogate_success) > 0 and len(exact_success) > 0:
            if surrogate_success[0] and exact_success[0]:
                maps_both_success.append(instance)

    print(f"\n=== RSSI Gap Analysis ===")
    print(f"Maps with both methods successful: {len(maps_both_success)}")

    # Collect detailed data
    analysis_data = []

    for instance in maps_both_success:
        map_name = instance.replace('.txt', '')
        instance_df = df[df['instance'] == instance]

        surrogate_rssi = instance_df[instance_df['method'] == 'surrogate']['mean_rssi'].values[0]
        exact_rssi = instance_df[instance_df['method'] == 'exact']['mean_rssi'].values[0]
        num_agents = instance_df['num_agents'].values[0]

        # Load detailed scores for distribution analysis
        surrogate_scores = load_all_scores(map_name, 'surrogate')
        exact_scores = load_all_scores(map_name, 'exact')

        rssi_gap = exact_rssi - surrogate_rssi  # Positive means exact is better
        rssi_gap_percent = (rssi_gap / exact_rssi) * 100

        analysis_data.append({
            'instance': instance,
            'map_name': map_name,
            'num_agents': num_agents,
            'surrogate_rssi': surrogate_rssi,
            'exact_rssi': exact_rssi,
            'rssi_gap': rssi_gap,
            'rssi_gap_percent': rssi_gap_percent,
            'surrogate_scores': surrogate_scores,
            'exact_scores': exact_scores,
            'num_surrogate_solutions': len(surrogate_scores) if surrogate_scores is not None else 0,
            'num_exact_solutions': len(exact_scores) if exact_scores is not None else 0
        })

    analysis_df = pd.DataFrame(analysis_data)

    # Print summary statistics
    print(f"\nRSSI Gap Statistics (Exact - Surrogate):")
    print(f"  Mean: {analysis_df['rssi_gap'].mean():.4f} dBm ({analysis_df['rssi_gap_percent'].mean():.2f}%)")
    print(f"  Median: {analysis_df['rssi_gap'].median():.4f} dBm ({analysis_df['rssi_gap_percent'].median():.2f}%)")
    print(f"  Std: {analysis_df['rssi_gap'].std():.4f} dBm")
    print(f"  Min: {analysis_df['rssi_gap'].min():.4f} dBm (best case)")
    print(f"  Max: {analysis_df['rssi_gap'].max():.4f} dBm (worst case)")

    # Identify typical and worst cases
    median_idx = (analysis_df['rssi_gap'] - analysis_df['rssi_gap'].median()).abs().idxmin()
    worst_idx = analysis_df['rssi_gap'].idxmax()
    best_idx = analysis_df['rssi_gap'].idxmin()

    print(f"\nCase Identification:")
    print(f"  Best case (smallest gap): {analysis_df.loc[best_idx, 'instance']} (gap={analysis_df.loc[best_idx, 'rssi_gap']:.4f} dBm)")
    print(f"  Typical case (median gap): {analysis_df.loc[median_idx, 'instance']} (gap={analysis_df.loc[median_idx, 'rssi_gap']:.4f} dBm)")
    print(f"  Worst case (largest gap): {analysis_df.loc[worst_idx, 'instance']} (gap={analysis_df.loc[worst_idx, 'rssi_gap']:.4f} dBm)")

    return analysis_df

def plot_rssi_gap_distribution(analysis_df):
    """Create RSSI gap distribution plot."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. Histogram of RSSI gaps
    ax1 = axes[0, 0]
    ax1.hist(analysis_df['rssi_gap'], bins=15, alpha=0.7, color='#3498db', edgecolor='black')
    ax1.axvline(analysis_df['rssi_gap'].mean(), color='red', linestyle='--', linewidth=2, label=f'Mean: {analysis_df["rssi_gap"].mean():.2f} dBm')
    ax1.axvline(analysis_df['rssi_gap'].median(), color='green', linestyle='--', linewidth=2, label=f'Median: {analysis_df["rssi_gap"].median():.2f} dBm')
    ax1.set_xlabel('RSSI Gap (Exact - Surrogate) [dBm]', fontweight='bold')
    ax1.set_ylabel('Frequency', fontweight='bold')
    ax1.set_title('Distribution of RSSI Gaps', fontweight='bold', fontsize=12)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. RSSI gap vs number of agents
    ax2 = axes[0, 1]
    ax2.scatter(analysis_df['num_agents'], analysis_df['rssi_gap'], s=100, alpha=0.6, color='#e74c3c')
    z = np.polyfit(analysis_df['num_agents'], analysis_df['rssi_gap'], 1)
    p = np.poly1d(z)
    ax2.plot(analysis_df['num_agents'], p(analysis_df['num_agents']), "r--", alpha=0.8, linewidth=2)
    ax2.set_xlabel('Number of Agents', fontweight='bold')
    ax2.set_ylabel('RSSI Gap (Exact - Surrogate) [dBm]', fontweight='bold')
    ax2.set_title('RSSI Gap vs Problem Size', fontweight='bold', fontsize=12)
    ax2.grid(True, alpha=0.3)

    # Add correlation coefficient
    corr = analysis_df['num_agents'].corr(analysis_df['rssi_gap'])
    ax2.text(0.05, 0.95, f'Correlation: {corr:.3f}', transform=ax2.transAxes,
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5), verticalalignment='top')

    # 3. Comparison of mean RSSI values
    ax3 = axes[1, 0]
    x = np.arange(len(analysis_df))
    width = 0.35

    bars1 = ax3.bar(x - width/2, analysis_df['exact_rssi'], width, label='Exact', alpha=0.8, color='#2ecc71')
    bars2 = ax3.bar(x + width/2, analysis_df['surrogate_rssi'], width, label='Surrogate', alpha=0.8, color='#e67e22')

    ax3.set_xlabel('Instance', fontweight='bold')
    ax3.set_ylabel('Mean RSSI [dBm]', fontweight='bold')
    ax3.set_title('RSSI Comparison by Instance', fontweight='bold', fontsize=12)
    ax3.set_xticks(x)
    ax3.set_xticklabels([f"M{int(m)}" for m in analysis_df['num_agents']], rotation=45)
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')

    # 4. Percentage degradation
    ax4 = axes[1, 1]
    colors = ['#27ae60' if x < 2 else '#f39c12' if x < 4 else '#c0392b' for x in abs(analysis_df['rssi_gap_percent'])]
    bars = ax4.barh(range(len(analysis_df)), analysis_df['rssi_gap_percent'], color=colors, alpha=0.7)
    ax4.set_yticks(range(len(analysis_df)))
    ax4.set_yticklabels([f"M{int(m)}" for m in analysis_df['num_agents']])
    ax4.set_xlabel('RSSI Degradation (%)', fontweight='bold')
    ax4.set_ylabel('Instance', fontweight='bold')
    ax4.set_title('Percentage RSSI Quality Change', fontweight='bold', fontsize=12)
    ax4.axvline(0, color='black', linestyle='-', linewidth=0.8)
    ax4.grid(True, alpha=0.3, axis='x')

    # Add color legend
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor='#27ae60', label='<2% degradation'),
                      Patch(facecolor='#f39c12', label='2-4% degradation'),
                      Patch(facecolor='#c0392b', label='>4% degradation')]
    ax4.legend(handles=legend_elements, loc='lower right')

    plt.tight_layout()
    plt.savefig('benchmark_results_mainpy/rssi_gap_distribution.png', dpi=300, bbox_inches='tight')
    print("\nPlot saved: benchmark_results_mainpy/rssi_gap_distribution.png")

def analyze_solution_quality_correlation(analysis_df):
    """Analyze correlation between number of solutions and RSSI quality."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Solution count comparison
    ax1 = axes[0]
    x = np.arange(len(analysis_df))
    width = 0.35

    bars1 = ax1.bar(x - width/2, analysis_df['num_exact_solutions'], width,
                    label='Exact', alpha=0.8, color='#3498db')
    bars2 = ax1.bar(x + width/2, analysis_df['num_surrogate_solutions'], width,
                    label='Surrogate', alpha=0.8, color='#e74c3c')

    ax1.set_xlabel('Instance', fontweight='bold')
    ax1.set_ylabel('Number of Solutions Found', fontweight='bold')
    ax1.set_title('Solution Diversity: Exact vs Surrogate', fontweight='bold', fontsize=12)
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"M{int(m)}" for m in analysis_df['num_agents']], rotation=45)
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.set_yscale('log')

    # Correlation: solution ratio vs RSSI gap
    ax2 = axes[1]
    solution_ratio = analysis_df['num_exact_solutions'] / (analysis_df['num_surrogate_solutions'] + 1)
    ax2.scatter(solution_ratio, abs(analysis_df['rssi_gap']), s=100, alpha=0.6, color='#9b59b6')

    # Add trend line
    valid_mask = np.isfinite(solution_ratio) & np.isfinite(analysis_df['rssi_gap'])
    if valid_mask.sum() > 1:
        z = np.polyfit(solution_ratio[valid_mask], abs(analysis_df['rssi_gap'][valid_mask]), 1)
        p = np.poly1d(z)
        x_trend = np.linspace(solution_ratio.min(), solution_ratio.max(), 100)
        ax2.plot(x_trend, p(x_trend), "r--", alpha=0.8, linewidth=2)

        corr = np.corrcoef(solution_ratio[valid_mask], abs(analysis_df['rssi_gap'][valid_mask]))[0, 1]
        ax2.text(0.05, 0.95, f'Correlation: {corr:.3f}', transform=ax2.transAxes,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5), verticalalignment='top')

    ax2.set_xlabel('Solution Exploration Ratio (Exact/Surrogate)', fontweight='bold')
    ax2.set_ylabel('|RSSI Gap| [dBm]', fontweight='bold')
    ax2.set_title('Solution Diversity vs RSSI Quality', fontweight='bold', fontsize=12)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('benchmark_results_mainpy/solution_quality_correlation.png', dpi=300, bbox_inches='tight')
    print("Plot saved: benchmark_results_mainpy/solution_quality_correlation.png")

def create_tradeoff_plot(analysis_df):
    """Create comprehensive runtime vs RSSI quality tradeoff plot."""
    # Load runtime data
    df = pd.read_csv('timing_results_mainpy/results.csv')

    # Merge with analysis data
    runtime_data = []
    for _, row in analysis_df.iterrows():
        instance_df = df[df['instance'] == row['instance']]
        surrogate_time = instance_df[instance_df['method'] == 'surrogate']['elapsed_time'].values[0]
        exact_time = instance_df[instance_df['method'] == 'exact']['elapsed_time'].values[0]

        runtime_data.append({
            'num_agents': row['num_agents'],
            'rssi_gap': abs(row['rssi_gap']),
            'rssi_gap_percent': abs(row['rssi_gap_percent']),
            'time_saved': exact_time - surrogate_time,
            'speedup': exact_time / surrogate_time,
            'exact_time': exact_time,
            'surrogate_time': surrogate_time
        })

    tradeoff_df = pd.DataFrame(runtime_data)

    fig, ax = plt.subplots(figsize=(10, 7))

    # Scatter plot with size proportional to speedup
    scatter = ax.scatter(tradeoff_df['rssi_gap_percent'],
                        tradeoff_df['time_saved'] / 60,  # Convert to minutes
                        s=tradeoff_df['num_agents'] * 10,
                        c=tradeoff_df['speedup'],
                        cmap='RdYlGn',
                        alpha=0.7,
                        edgecolors='black',
                        linewidth=1.5)

    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Speedup Factor', fontweight='bold', fontsize=11)

    # Annotate points
    for idx, row in tradeoff_df.iterrows():
        ax.annotate(f"M{int(row['num_agents'])}",
                   (row['rssi_gap_percent'], row['time_saved'] / 60),
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=9, fontweight='bold')

    ax.set_xlabel('RSSI Quality Loss (%)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Time Saved (minutes)', fontweight='bold', fontsize=12)
    ax.set_title('Runtime vs RSSI Quality Tradeoff\n(Bubble size = number of agents)',
                fontweight='bold', fontsize=14)
    ax.grid(True, alpha=0.3)

    # Add quadrant lines
    median_rssi = tradeoff_df['rssi_gap_percent'].median()
    median_time = tradeoff_df['time_saved'].median() / 60
    ax.axvline(median_rssi, color='gray', linestyle='--', alpha=0.5, linewidth=1)
    ax.axhline(median_time, color='gray', linestyle='--', alpha=0.5, linewidth=1)

    # Add text boxes for interpretation
    ax.text(0.02, 0.98, 'Ideal Zone:\nLow RSSI loss\nHigh time savings',
           transform=ax.transAxes, fontsize=9,
           bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7),
           verticalalignment='top')

    plt.tight_layout()
    plt.savefig('benchmark_results_mainpy/runtime_rssi_tradeoff.png', dpi=300, bbox_inches='tight')
    print("Plot saved: benchmark_results_mainpy/runtime_rssi_tradeoff.png")

    # Print summary
    print(f"\n=== Tradeoff Analysis ===")
    print(f"Average RSSI degradation: {tradeoff_df['rssi_gap_percent'].mean():.2f}%")
    print(f"Average time saved: {tradeoff_df['time_saved'].mean()/60:.1f} minutes")
    print(f"Average speedup: {tradeoff_df['speedup'].mean():.2f}x")
    print(f"\nTradeoff ratio: {(tradeoff_df['time_saved'].mean()/60) / tradeoff_df['rssi_gap_percent'].mean():.2f} minutes saved per 1% RSSI loss")

if __name__ == "__main__":
    print("=" * 60)
    print("RSSI Quality Tradeoff Analysis")
    print("Surrogate vs Exact Distance Computation")
    print("=" * 60)

    # Analyze RSSI gaps
    analysis_df = analyze_rssi_gaps()

    # Create visualizations
    plot_rssi_gap_distribution(analysis_df)
    analyze_solution_quality_correlation(analysis_df)
    create_tradeoff_plot(analysis_df)

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)
