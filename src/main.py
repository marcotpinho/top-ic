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
    parser.add_argument("--headings",type=int,default=4)
    parser.add_argument("--speed-fractions",type=float,nargs="+",default=[0,.5,1])
    parser.add_argument("--disable",nargs="*",default=[])
    parser.add_argument("--output")
    args=parser.parse_args()
    try:
        config=Config(mode=args.mode,seed=args.seed,max_seconds=args.max_seconds,max_evaluations=args.max_evaluations,
                      max_iterations=args.max_iterations,headings=args.headings,speed_fractions=tuple(args.speed_fractions),
                      disabled=tuple(args.disable),algorithm=args.algorithm)
        problem=load_problem_instance(args.instance) if args.instance else smoke_problem(2 if args.mode=="team_kop" else 1)
        result=run_optimization(problem,config)
        if args.output:save_result(result,args.output)
        print(json.dumps({"status":result.status,"elapsed_seconds":result.elapsed_seconds,"evaluations":result.statistics.get("evaluated",0),
                          "front":[s.objectives for s in result.front]},indent=2))
        return 0 if result.front else 1
    except ValueError as exc:
        parser.error(str(exc))


if __name__=="__main__":raise SystemExit(main())
