import numpy as np
import time
import json
from pathlib import Path
import sys

from src.entities.Map import Map
from src.entities.Evaluator import Evaluator, get_time_to_rewards, calculate_max_distance
from src.entities.Solution import Solution
from src.dist_func_batch import predict_max_distance_batch

def generate_synthetic_map(N):
    """Generate a synthetic map with N reward points"""
    np.random.seed(42)

    # Random positions in a 1000x1000 grid
    rpositions = np.random.rand(N, 2) * 1000

    # Random reward values
    rvalues = np.random.rand(N) * 10

    # Distance matrix
    distmx = np.zeros((N, N))
    for i in range(N):
        for j in range(N):
            if i != j:
                distmx[i, j] = np.linalg.norm(rpositions[i] - rpositions[j])

    # Create a mock map object
    class MockMap:
        def __init__(self):
            self.rpositions = rpositions
            self.rvalues = rvalues
            self.distmx = distmx
            self.diag = np.sqrt((1000**2) + (1000**2))
            self.center = np.array([500, 500])

    return MockMap()

def generate_synthetic_paths(M, N, map_obj):
    """Generate M synthetic paths covering the N reward points"""
    np.random.seed(42)

    paths = []
    nodes_per_agent = N // M
    remaining = N % M

    all_nodes = list(range(N))
    np.random.shuffle(all_nodes)

    start_idx = 0
    for i in range(M):
        # Distribute nodes across agents
        end_idx = start_idx + nodes_per_agent + (1 if i < remaining else 0)
        agent_nodes = all_nodes[start_idx:end_idx]

        if len(agent_nodes) > 0:
            paths.append(np.array(agent_nodes, dtype=np.int32))
        else:
            paths.append(np.array([0], dtype=np.int32))

        start_idx = end_idx

    return paths

def benchmark_exact_rssi(M, N, num_iterations=10):
    """Benchmark exact RSSI calculation"""
    map_obj = generate_synthetic_map(N)
    paths = generate_synthetic_paths(M, N, map_obj)
    speeds = np.array([2.0 + i * 0.1 for i in range(M)])

    times = []

    for _ in range(num_iterations):
        start = time.perf_counter()

        # Time only the RSSI calculation part
        interesting_times, timestamps = get_time_to_rewards(paths, speeds, map_obj.distmx)

        # Interpolate positions
        evaluator = Evaluator(map=map_obj, predict_distances=False)
        interpolated_positions = evaluator.interpolate_positions(paths, speeds, interesting_times)

        # Calculate max distance
        max_distance = calculate_max_distance(interpolated_positions)

        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to milliseconds

    return np.mean(times), np.std(times)

def benchmark_surrogate_rssi(M, N, num_iterations=10):
    """Benchmark surrogate model RSSI prediction"""
    map_obj = generate_synthetic_map(N)
    paths = generate_synthetic_paths(M, N, map_obj)
    speeds = np.array([2.0 + i * 0.1 for i in range(M)])

    # Prepare coordinates
    coordinates = [map_obj.rpositions[path] for path in paths]

    times = []

    for _ in range(num_iterations):
        start = time.perf_counter()

        # Time only the surrogate prediction
        empty_timestamps = []  # Surrogate doesn't use timestamps
        max_distances = predict_max_distance_batch([coordinates], [empty_timestamps], speeds, map_obj)

        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to milliseconds

    return np.mean(times), np.std(times)

def run_benchmarks():
    """Run comprehensive benchmarks across different M and N values"""

    # Parameter ranges
    M_values = [2, 4, 6, 8, 10, 15, 20, 30, 50, 75, 100]
    N_values = [10, 20, 30, 50, 75, 100, 150, 200]

    results = {
        'M_values': M_values,
        'N_values': N_values,
        'exact_times': {},
        'surrogate_times': {},
        'exact_stds': {},
        'surrogate_stds': {}
    }

    total_tests = len(M_values) * len(N_values)
    current_test = 0

    print("="*70)
    print("RSSI CALCULATION BENCHMARK")
    print("="*70)
    print(f"\nRunning {total_tests} benchmark tests...")
    print(f"M values: {M_values}")
    print(f"N values: {N_values}")
    print("\nProgress:")

    for M in M_values:
        for N in N_values:
            current_test += 1

            # Skip if N < M (doesn't make sense)
            if N < M:
                continue

            key = f"{M}_{N}"

            print(f"[{current_test}/{total_tests}] Testing M={M}, N={N}...", end=" ", flush=True)

            try:
                # Benchmark exact method
                exact_mean, exact_std = benchmark_exact_rssi(M, N, num_iterations=5)
                results['exact_times'][key] = exact_mean
                results['exact_stds'][key] = exact_std

                # Benchmark surrogate method
                surrogate_mean, surrogate_std = benchmark_surrogate_rssi(M, N, num_iterations=5)
                results['surrogate_times'][key] = surrogate_mean
                results['surrogate_stds'][key] = surrogate_std

                speedup = exact_mean / surrogate_mean if surrogate_mean > 0 else 0
                print(f"Exact: {exact_mean:.2f}ms, Surrogate: {surrogate_mean:.2f}ms, Speedup: {speedup:.2f}x")

            except Exception as e:
                print(f"FAILED: {e}")
                results['exact_times'][key] = None
                results['surrogate_times'][key] = None
                results['exact_stds'][key] = None
                results['surrogate_stds'][key] = None

    # Save results
    output_file = Path("benchmark_results/rssi_timing_results.json")
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*70}")
    print(f"Results saved to {output_file}")
    print(f"{'='*70}")

    return results

if __name__ == "__main__":
    results = run_benchmarks()

    print("\n" + "="*70)
    print("BENCHMARK SUMMARY")
    print("="*70)

    # Find best and worst speedups
    speedups = []
    for key in results['exact_times']:
        if results['exact_times'][key] is not None and results['surrogate_times'][key] is not None:
            if results['surrogate_times'][key] > 0:
                speedup = results['exact_times'][key] / results['surrogate_times'][key]
                M, N = map(int, key.split('_'))
                speedups.append((M, N, speedup))

    if speedups:
        speedups.sort(key=lambda x: x[2])

        print(f"\nWorst speedup (smallest):")
        M, N, speedup = speedups[0]
        print(f"  M={M}, N={N}: {speedup:.2f}x")

        print(f"\nBest speedup (largest):")
        M, N, speedup = speedups[-1]
        print(f"  M={M}, N={N}: {speedup:.2f}x")

        avg_speedup = np.mean([s[2] for s in speedups])
        print(f"\nAverage speedup: {avg_speedup:.2f}x")

    print("="*70)
