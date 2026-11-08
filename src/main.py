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
        "--initialization-budget-fraction",
        type=float,
        default=0.2,
        help="maximum fraction of time and exact-evaluation budgets used by initialization",
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
        default=100,
        help="maximum epsilon-front representatives before box coarsening",
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
        "--velocity-segment-lengths",
        type=int,
        nargs="+",
        default=[2, 3],
        help="visit counts for contiguous velocity-change blocks",
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
        default=100,
        help="maximum physically valid dominated solutions kept for search bases",
    )
    parser.add_argument(
        "--disable-pool-selection",
        action="store_true",
        help="ablation: update the coverage pool but select search bases only from F",
    )
    parser.add_argument(
        "--selection-policy",
        choices=["nd_count", "legacy_fraction"],
        default="nd_count",
        help="archive selection rule; legacy_fraction reproduces the pre-correction ablation",
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
        "--neighborhood-candidates",
        type=int,
        default=120,
        help="maximum sampled proposals generated per neighborhood call",
    )
    parser.add_argument("--output", help="path for the complete JSON run result")
    parser.add_argument(
        "--free-segment-radius",
        type=float,
        help="maximum lateral FREE offset from a route segment; defaults to communication range",
    )
    return parser


def _config(args: argparse.Namespace) -> Config:
    return Config(
        seed=args.seed,
        max_seconds=args.max_seconds,
        max_evaluations=args.max_evaluations,
        max_iterations=args.max_iterations,
        initialization_budget_fraction=args.initialization_budget_fraction,
        neighborhood_hv_tau=args.neighborhood_hv_tau,
        neighborhood_max_passes=args.neighborhood_max_passes,
        archive_size=args.archive_size,
        eps_reward=args.eps_reward,
        eps_time=args.eps_time,
        headings=args.headings,
        speed_fractions=tuple(args.speed_fractions),
        velocity_segment_lengths=tuple(args.velocity_segment_lengths),
        disabled=tuple(args.disable),
        comm_range=args.comm_range,
        handshake_time=args.handshake_time,
        recurrence_bound=args.recurrence_bound,
        dominated_archive_size=args.dominated_archive_size,
        pool_selection_enabled=not args.disable_pool_selection,
        selection_policy=args.selection_policy,
        waypoint_workspace=tuple(args.waypoint_workspace)
        if args.waypoint_workspace
        else None,
        waypoint_steps=tuple(args.waypoint_steps),
        neighborhood_candidates=args.neighborhood_candidates,
        free_segment_radius=args.free_segment_radius,
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
