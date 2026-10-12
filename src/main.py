"""CLI for the team KOP with intermittent communication."""

import argparse
import json

from .config import Config
from .environment import load_problem_instance, smoke_problem
from .solver import run_optimization, save_result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TOP-ICC sampled MOVNS search")
    parser.add_argument("--instance")
    parser.add_argument("--mode", choices=["team_kop_icc"], default="team_kop_icc")
    parser.add_argument("--algorithm", choices=["movns"], default="movns")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-seconds", type=float, default=30.0)
    parser.add_argument("--max-evaluations", type=int, default=2000)
    parser.add_argument("--max-iterations", type=int, default=100)
    parser.add_argument("--archive-size", type=int, default=200)
    parser.add_argument("--front-selection-prob", type=float, default=0.9)
    parser.add_argument("--eps-reward", type=float, default=1.0)
    parser.add_argument("--eps-time", type=float, default=0.1)
    parser.add_argument("--eps-violation", type=float)
    parser.add_argument("--headings", type=int, default=4)
    parser.add_argument("--speed-fractions", type=float, nargs="+", default=[0, 0.5, 1])
    parser.add_argument("--disable", nargs="*", default=[])
    parser.add_argument("--comm-range", type=float, default=2.0)
    parser.add_argument("--handshake-time", type=float, default=0.5)
    parser.add_argument("--recurrence-bound", type=float, default=5.0)
    parser.add_argument("--dominated-archive-size", type=int, default=40)
    parser.add_argument("--max-free-waypoints", type=int, default=3)
    parser.add_argument("--waypoint-workspace", type=float, nargs=4)
    parser.add_argument("--waypoint-steps", type=float, nargs="+", default=[1.0, 0.25])
    parser.add_argument("--wait-steps", type=float, nargs="+", default=[0.25, 1.0])
    parser.add_argument("--neighborhood-candidates", type=int, default=120)
    parser.add_argument("--output")
    return parser


def _config(args: argparse.Namespace) -> Config:
    return Config(
        mode=args.mode,
        algorithm=args.algorithm,
        seed=args.seed,
        max_seconds=args.max_seconds,
        max_evaluations=args.max_evaluations,
        max_iterations=args.max_iterations,
        archive_size=args.archive_size,
        front_selection_prob=args.front_selection_prob,
        eps_reward=args.eps_reward,
        eps_time=args.eps_time,
        eps_violation=args.eps_violation,
        headings=args.headings,
        speed_fractions=tuple(args.speed_fractions),
        disabled=tuple(args.disable),
        comm_range=args.comm_range,
        handshake_time=args.handshake_time,
        recurrence_bound=args.recurrence_bound,
        dominated_archive_size=args.dominated_archive_size,
        max_free_waypoints=args.max_free_waypoints,
        waypoint_workspace=tuple(args.waypoint_workspace)
        if args.waypoint_workspace
        else None,
        waypoint_steps=tuple(args.waypoint_steps),
        wait_steps=tuple(args.wait_steps),
        neighborhood_candidates=args.neighborhood_candidates,
    )


def main() -> int:
    """Run the ICC search and optionally save complete evaluation records."""
    parser = _parser()
    args = parser.parse_args()
    try:
        config = _config(args)
        problem = (
            load_problem_instance(args.instance) if args.instance else smoke_problem(2)
        )
        result = run_optimization(problem, config)
        if args.output:
            save_result(result, args.output)
        summary = {
            "status": result.status,
            "elapsed_seconds": result.elapsed_seconds,
            "evaluations": result.statistics.get("evaluated", 0),
            "profiling": result.statistics["profiling"],
            "front": [solution.objectives for solution in result.front],
        }
        print(json.dumps(summary, indent=2))
        return 0 if result.front else 1
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
