"""Run a bounded KOP search from a versioned seconds-budget instance."""
import argparse
import json
from .config import Config
from .environment import load_problem_instance,smoke_problem
from .solver import run_optimization,save_result


def main():
    parser=argparse.ArgumentParser(description="MOVNS for acceleration-aware KOP")
    parser.add_argument("--instance")
    parser.add_argument("--mode",choices=["single_kop","team_kop","team_kop_icc"],default="single_kop")
    parser.add_argument("--algorithm",choices=["movns","lns"],default="movns")
    parser.add_argument("--seed",type=int,default=42)
    parser.add_argument("--max-seconds",type=float,default=30.)
    parser.add_argument("--max-evaluations",type=int,default=2000)
    parser.add_argument("--max-iterations",type=int,default=100)
    parser.add_argument("--archive-size",type=int,default=200)
    parser.add_argument("--front-selection-prob",type=float,default=.9)
    parser.add_argument("--eps-reward",type=float,default=1.0)
    parser.add_argument("--eps-time",type=float,default=0.1)
    parser.add_argument("--eps-delta",type=float)
    parser.add_argument("--eps-violation",type=float)
    parser.add_argument("--tc-sweep",type=float,nargs="*",default=[])
    parser.add_argument("--headings",type=int,default=4)
    parser.add_argument("--speed-fractions",type=float,nargs="+",default=[0,.5,1])
    parser.add_argument("--disable",nargs="*",default=[])
    parser.add_argument("--comm-range",type=float,default=2.)
    parser.add_argument("--handshake-time",type=float,default=.5)
    parser.add_argument("--recurrence-bound",type=float,default=5.)
    parser.add_argument("--dominated-archive-size",type=int,default=40)
    parser.add_argument("--working-pool-size",type=int,help=argparse.SUPPRESS)
    parser.add_argument("--max-free-waypoints",type=int,default=3)
    parser.add_argument("--waypoint-workspace",type=float,nargs=4)
    parser.add_argument("--waypoint-steps",type=float,nargs="+",default=[1.,.25])
    parser.add_argument("--wait-steps",type=float,nargs="+",default=[.25,1.])
    parser.add_argument("--neighborhood-candidates",type=int,default=120)
    parser.add_argument("--output")
    args=parser.parse_args()
    try:
        config=Config(mode=args.mode,seed=args.seed,max_seconds=args.max_seconds,max_evaluations=args.max_evaluations,
                      archive_size=args.archive_size,front_selection_prob=args.front_selection_prob,
                      max_iterations=args.max_iterations,eps_reward=args.eps_reward,eps_time=args.eps_time,
                      eps_delta=args.eps_delta,eps_violation=args.eps_violation,tc_sweep=tuple(args.tc_sweep),headings=args.headings,speed_fractions=tuple(args.speed_fractions),
                      disabled=tuple(args.disable),algorithm=args.algorithm,
                      comm_range=args.comm_range,handshake_time=args.handshake_time,recurrence_bound=args.recurrence_bound,
                      dominated_archive_size=args.dominated_archive_size,working_pool_size=args.working_pool_size,
                      max_free_waypoints=args.max_free_waypoints,
                      waypoint_workspace=tuple(args.waypoint_workspace) if args.waypoint_workspace else None,
                      waypoint_steps=tuple(args.waypoint_steps),wait_steps=tuple(args.wait_steps),neighborhood_candidates=args.neighborhood_candidates)
        problem=load_problem_instance(args.instance) if args.instance else smoke_problem(2 if args.mode in ("team_kop","team_kop_icc") else 1)
        result=run_optimization(problem,config)
        if args.output:save_result(result,args.output)
        print(json.dumps({"status":result.status,"elapsed_seconds":result.elapsed_seconds,"evaluations":result.statistics.get("evaluated",0),
                          "front":[s.objectives for s in result.front]},indent=2))
        return 0 if result.front else 1
    except ValueError as exc:
        parser.error(str(exc))


if __name__=="__main__":raise SystemExit(main())
