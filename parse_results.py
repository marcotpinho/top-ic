#!/usr/bin/env python3
"""Parse results from main.py output pickle files."""
import sys
import pickle
from pathlib import Path
import numpy as np

def parse_results(map_name, method, speed="1.0", out_dir="out"):
    """Parse pickle files and extract metrics."""
    results_dir = Path(out_dir) / map_name / speed / method
    scores_file = results_dir / "scores.pkl"

    print(f"Parsing results from: {scores_file}", file=sys.stderr)

    if not scores_file.exists():
        print(f"No results found at: {scores_file}", file=sys.stderr)
        return None, None, 0

    # Read all scores from pickle file
    scores = []
    try:
        with open(scores_file, 'rb') as f:
            while True:
                try:
                    score = pickle.load(f)
                    scores.append(score)
                    print(f"Loaded score: {score}", file=sys.stderr)
                except EOFError:
                    break
    except Exception as e:
        print(f"Error reading {scores_file}: {e}", file=sys.stderr)
        return None, None, 0

    if len(scores) == 0:
        return None, None, 0

    scores = np.array(scores)

    # Extract metrics
    # score[0] = reward, score[1] = rssi
    total_reward = np.max(scores[:, 0])
    mean_rssi = np.mean(scores[:, 1])
    num_solutions = len(scores)

    return total_reward, mean_rssi, num_solutions

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: parse_results.py <map_name> <method> [speed] [out_dir]")
        sys.exit(1)

    map_name = sys.argv[1]
    method = sys.argv[2]
    speed = sys.argv[3] if len(sys.argv) > 3 else "1.0"
    out_dir = sys.argv[4] if len(sys.argv) > 4 else "out"
    print(f"Arguments - map_name: {map_name}, method: {method}, speed: {speed}, out_dir: {out_dir}", file=sys.stderr)

    total_reward, mean_rssi, num_solutions = parse_results(map_name, method, speed, out_dir)

    if total_reward is not None:
        print(f"{total_reward},{mean_rssi},{num_solutions}")
    else:
        print("0,0,0")
