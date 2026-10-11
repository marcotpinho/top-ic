"""Supported CLI; communication mode is explicitly not implemented yet."""
import argparse
import json
from .environment import load_problem_instance, smoke_problem
from .solution import direct_solution
from .evaluator import Evaluator


def main():
    parser=argparse.ArgumentParser(description="Acceleration-aware KOP foundation")
    parser.add_argument("--instance")
    parser.add_argument("--mode",choices=["single_kop","team_kop","team_kop_icc"],default="single_kop")
    args=parser.parse_args()
    if args.mode!="single_kop":
        parser.error("Only single-agent trajectory construction is implemented in step 1")
    try:
        problem=load_problem_instance(args.instance) if args.instance else smoke_problem()
        result=Evaluator(problem).evaluate(direct_solution(problem)).evaluation
        print(json.dumps({"valid":result.valid,"objectives":result.objectives,"completion_times":result.completion_times,"reason":result.reason},indent=2))
        return 0 if result.valid else 1
    except ValueError as exc:
        parser.error(str(exc))


if __name__=="__main__":
    raise SystemExit(main())
