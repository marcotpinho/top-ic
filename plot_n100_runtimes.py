import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Read the results
df = pd.read_csv('timing_results_mainpy/results.csv')

# Filter for maps M2_N100 to M50_N100
maps_of_interest = ['M2_N100.txt', 'M3_N100.txt', 'M5_N100.txt', 'M10_N100.txt',
                    'M20_N100.txt', 'M30_N100.txt', 'M50_N100.txt']

df_filtered = df[df['instance'].isin(maps_of_interest)]

# Extract number of agents from instance name for sorting
df_filtered['num_agents_sort'] = df_filtered['instance'].str.extract(r'M(\d+)_N100\.txt').astype(int)
df_filtered = df_filtered.sort_values('num_agents_sort')

# Pivot to get surrogate and exact in separate columns
pivot_df = df_filtered.pivot(index='num_agents_sort', columns='method', values='elapsed_time')

# Create the plot
fig, ax = plt.subplots(figsize=(10, 6))

x = np.arange(len(pivot_df.index))
width = 0.35

bars1 = ax.bar(x - width/2, pivot_df['surrogate'], width, label='Surrogate', alpha=0.8, color='#2ecc71')
bars2 = ax.bar(x + width/2, pivot_df['exact'], width, label='Exact', alpha=0.8, color='#e74c3c')

# Customize the plot
ax.set_xlabel('Number of Agents', fontsize=12, fontweight='bold')
ax.set_ylabel('Runtime (seconds)', fontsize=12, fontweight='bold')
ax.set_title('Runtime Comparison: Surrogate vs Exact Methods\n(N=100 waypoints)',
             fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(pivot_df.index)
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3, axis='y')

# Add value labels on bars
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}s',
                ha='center', va='bottom', fontsize=9)

plt.tight_layout()
plt.savefig('benchmark_results_mainpy/n100_runtime_comparison.png', dpi=300, bbox_inches='tight')
print("Plot saved to: benchmark_results_mainpy/n100_runtime_comparison.png")

# Print summary statistics
print("\n=== Runtime Summary ===")
print(f"\nSurrogate method:")
print(f"  Min: {pivot_df['surrogate'].min():.0f}s (M={pivot_df['surrogate'].idxmin()} agents)")
print(f"  Max: {pivot_df['surrogate'].max():.0f}s (M={pivot_df['surrogate'].idxmax()} agents)")
print(f"  Mean: {pivot_df['surrogate'].mean():.0f}s")

print(f"\nExact method:")
print(f"  Min: {pivot_df['exact'].min():.0f}s (M={pivot_df['exact'].idxmin()} agents)")
print(f"  Max: {pivot_df['exact'].max():.0f}s (M={pivot_df['exact'].idxmax()} agents)")
print(f"  Mean: {pivot_df['exact'].mean():.0f}s")

print(f"\nSpeedup (Exact/Surrogate):")
speedup = pivot_df['exact'] / pivot_df['surrogate']
print(f"  Min: {speedup.min():.2f}x (M={speedup.idxmin()} agents)")
print(f"  Max: {speedup.max():.2f}x (M={speedup.idxmax()} agents)")
print(f"  Mean: {speedup.mean():.2f}x")
