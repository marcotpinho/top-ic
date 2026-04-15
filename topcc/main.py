"""CLI entry point for TOP-CC optimization."""

import argparse
import numpy as np
from pathlib import Path

from topcc.config import Config
from topcc.environment import load_problem_instance
from topcc.solver import run_optimization


def main() -> None:
    try:
        args = _parse_args()

        print(f"Loading problem instance from: {args.map}")
        num_rewards, num_agents, default_budget, default_speeds, rpositions, rvalues = (
            load_problem_instance(args.map)
        )
        print(f"Problem instance: {num_agents} agents, {num_rewards} rewards")

        budget, speeds = _validate_params(args, num_agents, default_budget, default_speeds)

        map_name = Path(args.map).stem
        config = Config(
            seed=args.seed,
            max_iterations=args.num_iterations,
            max_time=args.max_time,
            algorithm=args.algorithm,
            save_results=not args.no_save,
            plot_results=not args.no_plot,
            predict_distances=args.predict_distances,
            map_file=args.map,
            db_path=f"data/{map_name}_distances_train.json",
            save_to_db=args.save_to_db,
        )
        print(f"Configurations: {config}")

        print(f"Starting optimization with algorithm: {args.algorithm}")
        paths = run_optimization(
            rpositions=rpositions,
            rvalues=rvalues,
            budget=budget,
            map_name=map_name,
            num_agents=num_agents,
            speeds=speeds,
            config=config,
        )
        print(f"Optimization completed. Found {len(paths)} Pareto optimal solutions.")

    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        exit(1)
    except KeyboardInterrupt:
        print("\nOptimization interrupted by user.")
        exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        exit(1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run multi-objective optimization for multi-agent routing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--map", type=str, default="data/maps/1.txt", help="Path to map file")
    parser.add_argument("--out", type=str, default="out/", help="Output directory")
    parser.add_argument("--algorithm", type=str, default="unique_vis", choices=["unique_vis", "multi_vis"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max_time", type=int, default=540, help="Max execution time (seconds)")
    parser.add_argument("--num_iterations", type=int, default=100)
    parser.add_argument("--speeds", type=float, nargs="+", help="Per-agent speeds")
    parser.add_argument("--budget", type=float, nargs="+", help="Per-agent budgets")
    parser.add_argument("--no_save", action="store_true")
    parser.add_argument("--no_plot", action="store_true")
    parser.add_argument("--random_speeds", action="store_true")
    parser.add_argument("--random_budget", action="store_true")
    parser.add_argument("--save_to_db", action="store_true")
    parser.add_argument("--predict_distances", action="store_true")
    return parser.parse_args()


def _validate_params(args, num_agents, default_budget, default_speeds):
    budget = default_budget.copy()
    speeds = default_speeds.copy()

    if args.budget is not None:
        if len(args.budget) != num_agents:
            raise ValueError(f"Budget count ({len(args.budget)}) must match agents ({num_agents})")
        budget = args.budget
    elif args.random_budget:
        min_budget = default_budget[0]
        budget = list(np.random.randint(min_budget, 2 * min_budget, num_agents))

    if args.speeds is not None:
        if len(args.speeds) != num_agents:
            raise ValueError(f"Speed count ({len(args.speeds)}) must match agents ({num_agents})")
        speeds = args.speeds
    elif args.random_speeds:
        min_speed = default_speeds[0]
        speeds = list(np.random.uniform(min_speed, 3 * min_speed, num_agents))

    return budget, speeds


if __name__ == "__main__":
    main()
