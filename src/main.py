"""CLI for the team KOP with intermittent communication."""

import argparse
import json

from .config import Config
from .environment import load_problem_instance, smoke_problem
from .solver import run_optimization, save_result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TOP-ICC sampled MOVNS search",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--instance",
        help="instance JSON path; omitting it runs the built-in two-agent smoke map",
    )
    parser.add_argument(
        "--mode",
        choices=["team_kop_icc"],
        default="team_kop_icc",
        help="problem mode; only team KOP with intermittent communication is supported",
    )
    parser.add_argument(
        "--algorithm",
        choices=["movns"],
        default="movns",
        help="search algorithm; only sampled multi-objective VNS is supported",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="seed for the run's random generator"
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=30.0,
        help="search wall-time limit in seconds",
    )
    parser.add_argument(
        "--max-evaluations",
        type=int,
        default=2000,
        help="maximum distinct candidates sent through the evaluator",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=100,
        help="maximum outer local-search iterations",
    )
    parser.add_argument(
        "--neighborhood-hv-tau",
        type=float,
        default=0.0,
        help="minimum normalized archive hypervolume gain required to repeat a neighborhood",
    )
    parser.add_argument(
        "--neighborhood-max-passes",
        type=int,
        default=3,
        help="maximum passes per neighborhood in each outer iteration",
    )
    parser.add_argument(
        "--archive-size",
        type=int,
        default=200,
        help="maximum epsilon-front representatives before box coarsening",
    )
    parser.add_argument(
        "--front-selection-prob",
        type=float,
        default=0.9,
        help="probability of selecting a search base from the epsilon front",
    )
    parser.add_argument(
        "--eps-reward",
        type=float,
        default=1.0,
        help="epsilon-box width for negative reward units",
    )
    parser.add_argument(
        "--eps-time",
        type=float,
        default=0.1,
        help="epsilon-box width for mean completion time in seconds",
    )
    parser.add_argument(
        "--eps-violation",
        type=float,
        help="epsilon-box width for communication violation in seconds; default 1",
    )
    parser.add_argument(
        "--headings",
        type=int,
        default=4,
        help="number of heading directions in the visit-velocity menu",
    )
    parser.add_argument(
        "--speed-fractions",
        type=float,
        nargs="+",
        default=[0, 0.5, 1],
        help="fractions of each axis speed limit used in the velocity menu",
    )
    parser.add_argument(
        "--disable",
        nargs="*",
        default=[],
        help="ICC neighborhood family names to omit from the search",
    )
    parser.add_argument(
        "--comm-range",
        type=float,
        default=2.0,
        help="maximum Euclidean communication range in map distance units",
    )
    parser.add_argument(
        "--handshake-time",
        type=float,
        default=0.5,
        help="continuous contact time required before a later link becomes effective",
    )
    parser.add_argument(
        "--recurrence-bound",
        type=float,
        default=5.0,
        help="maximum allowed information staleness T_c in seconds",
    )
    parser.add_argument(
        "--dominated-archive-size",
        type=int,
        default=40,
        help="maximum physically valid dominated solutions kept for search bases",
    )
    parser.add_argument(
        "--max-free-waypoints",
        type=int,
        default=3,
        help="maximum free visits allowed on each agent route",
    )
    parser.add_argument(
        "--waypoint-workspace",
        type=float,
        nargs=4,
        metavar=("XMIN", "XMAX", "YMIN", "YMAX"),
        help="bounds for free waypoints; inferred from the instance when omitted",
    )
    parser.add_argument(
        "--waypoint-steps",
        type=float,
        nargs="+",
        default=[1.0, 0.25],
        help="distance steps used to propose or move free waypoints",
    )
    parser.add_argument(
        "--wait-steps",
        type=float,
        nargs="+",
        default=[0.25, 1.0],
        help="time steps in seconds used for stopped waits and meetings",
    )
    parser.add_argument(
        "--neighborhood-candidates",
        type=int,
        default=120,
        help="maximum sampled proposals generated per neighborhood call",
    )
    parser.add_argument("--output", help="path for the complete JSON run result")
    return parser


def _config(args: argparse.Namespace) -> Config:
    return Config(
        mode=args.mode,
        algorithm=args.algorithm,
        seed=args.seed,
        max_seconds=args.max_seconds,
        max_evaluations=args.max_evaluations,
        max_iterations=args.max_iterations,
        neighborhood_hv_tau=args.neighborhood_hv_tau,
        neighborhood_max_passes=args.neighborhood_max_passes,
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
