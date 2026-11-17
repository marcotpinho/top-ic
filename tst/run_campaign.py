"""Run C, D, E, and G6 campaign cells through scripts/run_experiment.py."""

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from generate_instances import generate

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_experiment.py"
INSTANCES = ROOT / "tst/instances"


@dataclass(frozen=True)
class Case:
    group: str
    name: str
    seed: int
    instance: str
    arguments: tuple[str, ...]


def base_arguments(instance, seed, evaluations, recurrence=5.0, radius=2.0):
    return (
        "--instance",
        instance,
        "--seed",
        str(seed),
        "--comm-range",
        str(radius),
        "--recurrence-bound",
        str(recurrence),
        "--max-seconds",
        "900",
        "--max-evaluations",
        str(evaluations),
        "--max-iterations",
        "1000000",
    )


def group_c(seeds, maps=("m2", "m3")):
    cases = []
    for map_name, instance in (
        ("m2", "tst/instances/icc-20s-2agents.json"),
        ("m3", "tst/instances/icc-20s-3agents.json"),
    ):
        if map_name not in maps:
            continue
        for recurrence in (0.05, 2, 5, 10, 100):
            for seed in seeds:
                label = str(recurrence).replace(".", "p")
                cases.append(
                    Case(
                        "C",
                        f"{map_name}-tc{label}-s{seed}",
                        seed,
                        instance,
                        base_arguments(instance, seed, 20000, recurrence),
                    )
                )
    return cases


def group_d(seeds):
    cases = []
    base = "tst/instances/icc-20s-2agents.json"
    for seed in seeds:
        for radius in (1, 2, 4, 8):
            cases.append(
                Case(
                    "D",
                    f"range-{radius}-s{seed}",
                    seed,
                    base,
                    base_arguments(base, seed, 5000, 5, radius),
                )
            )
        for agents in (2, 3, 5):
            instance = f"tst/instances/icc-20s-{agents}agents.json"
            cases.append(
                Case(
                    "D",
                    f"agents-{agents}-s{seed}",
                    seed,
                    instance,
                    base_arguments(instance, seed, 5000),
                )
            )
        for budget in (10, 20, 30):
            instance = f"tst/instances/icc-20s-budget{budget}.json"
            cases.append(
                Case(
                    "D",
                    f"budget-{budget}-s{seed}",
                    seed,
                    instance,
                    base_arguments(instance, seed, 5000),
                )
            )
        for label, instance in (
            ("clustered", base),
            ("scaled2", "tst/instances/icc-20s-scaled2.json"),
        ):
            cases.append(
                Case(
                    "D",
                    f"spread-{label}-s{seed}",
                    seed,
                    instance,
                    base_arguments(instance, seed, 5000),
                )
            )
        for agents in (2, 3):
            instance = f"tst/instances/bridge{agents}.json"
            cases.append(
                Case(
                    "D",
                    f"bridge-{agents}-s{seed}",
                    seed,
                    instance,
                    base_arguments(instance, seed, 5000, 0.05, 11),
                )
            )
        for speed in (1.5, 3.0, 6.0):
            label = str(speed).replace(".", "p")
            instance = f"tst/instances/icc-20s-speed{label}.json"
            cases.append(
                Case(
                    "D",
                    f"speed-{label}-s{seed}",
                    seed,
                    instance,
                    base_arguments(instance, seed, 5000),
                )
            )
    return cases


def group_e(seeds, include_m3=False):
    cases = []
    maps = [("m2", "tst/instances/icc-20s-2agents.json")]
    if include_m3:
        maps.append(("m3", "tst/instances/icc-20s-3agents.json"))
    disabled = (
        "remove",
        "replace",
        "assignment",
        "reorder",
        "insert",
        "relay",
        "free_near_visit",
        "free_segment",
        "unlink",
        "velocity_change",
        "velocity_segment",
    )
    for map_name, instance in maps:
        for seed in seeds:
            base = base_arguments(instance, seed, 5000)
            cases.append(Case("E", f"{map_name}-E0-base-s{seed}", seed, instance, base))
            for family in disabled:
                cases.append(
                    Case(
                        "E",
                        f"{map_name}-E1-no-{family}-s{seed}",
                        seed,
                        instance,
                        (*base, "--disable", family),
                    )
                )
            cases.append(
                Case(
                    "E",
                    f"{map_name}-E3-no-pool-selection-s{seed}",
                    seed,
                    instance,
                    (*base, "--disable-pool-selection"),
                )
            )
            cases.append(
                Case(
                    "E",
                    f"{map_name}-E2-no-communication-repair-s{seed}",
                    seed,
                    instance,
                    (*base, "--communication-repair-rounds", "0"),
                )
            )
            cases.append(
                Case(
                    "E",
                    f"{map_name}-E4-legacy-fraction-s{seed}",
                    seed,
                    instance,
                    (*base, "--selection-policy", "legacy_fraction"),
                )
            )
            cases.append(
                Case(
                    "E",
                    f"{map_name}-E8-no-free-s{seed}",
                    seed,
                    instance,
                    (*base, "--disable", "free_near_visit", "free_segment", "relay"),
                )
            )
            cases.append(
                Case(
                    "E",
                    f"{map_name}-E9-speed-one-s{seed}",
                    seed,
                    instance,
                    (*base, "--speed-fractions", "1"),
                )
            )
            cases.append(
                Case(
                    "E",
                    f"{map_name}-E9-headings-four-s{seed}",
                    seed,
                    instance,
                    (*base, "--headings", "4"),
                )
            )
            cases.append(
                Case(
                    "E",
                    f"{map_name}-E10-no-incremental-s{seed}",
                    seed,
                    instance,
                    (*base, "--disable-incremental-evaluation"),
                )
            )
            cases.append(
                Case(
                    "E",
                    f"{map_name}-E10-verify-incremental-s{seed}",
                    seed,
                    instance,
                    (*base, "--verify-incremental"),
                )
            )
            cases.append(
                Case(
                    "E",
                    f"{map_name}-E11-workers4-s{seed}",
                    seed,
                    instance,
                    (
                        *base,
                        "--evaluation-workers",
                        "4",
                        "--evaluation-batch-size",
                        "8",
                    ),
                )
            )
            cases.append(
                Case(
                    "E",
                    f"{map_name}-E6-no-ruin-recreate-s{seed}",
                    seed,
                    instance,
                    (*base, "--disable-ruin-recreate"),
                )
            )
    return cases


def group_g6():
    instance = "tst/instances/icc-20s-2agents.json"
    arguments = base_arguments(instance, 42, 2000)
    return [
        Case("G6", f"determinism-{replicate}", 42, instance, arguments)
        for replicate in (1, 2)
    ]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--group", action="append", choices=("C", "D", "E", "G6"), required=True
    )
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--maps", nargs="+", choices=("m2", "m3"), default=("m2", "m3"))
    parser.add_argument(
        "--output-root", default=f"results/plan-tests/{date.today().isoformat()}"
    )
    parser.add_argument("--include-m3", action="store_true")
    parser.add_argument("--batch-eval", action="store_true")
    parser.add_argument("--max-evaluations", type=int)
    parser.add_argument("--max-seconds", type=float)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--parallel", type=int, default=1)
    return parser.parse_args()


def build_cases(args):
    cases = []
    for group in args.group:
        seeds = args.seeds or (range(201, 211) if group == "E" else range(101, 111))
        if group == "C":
            cases.extend(group_c(seeds, args.maps))
        elif group == "D":
            cases.extend(group_d(seeds))
        elif group == "E":
            cases.extend(group_e(seeds, args.include_m3))
        else:
            cases.extend(group_g6())
    return cases


def main():
    args = parse_args()
    generate()
    output_root = ROOT / args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    ledger = []
    pending = []
    for case in build_cases(args):
        output = output_root / case.group / case.name
        arguments = list(case.arguments)
        if args.max_evaluations is not None:
            evaluations = arguments.index("--max-evaluations") + 1
            arguments[evaluations] = str(args.max_evaluations)
        if args.max_seconds is not None:
            seconds = arguments.index("--max-seconds") + 1
            arguments[seconds] = str(args.max_seconds)
        if args.pilot:
            evaluations = arguments.index("--max-evaluations") + 1
            seconds = arguments.index("--max-seconds") + 1
            arguments[evaluations] = "500"
            arguments[seconds] = "60"
        if args.batch_eval:
            arguments.append("--batch-eval")
        command = [
            str(ROOT / ".venv/bin/python"),
            str(RUNNER),
            "--output-dir",
            str(output.relative_to(ROOT)),
            "--",
            *arguments,
        ]
        row = {
            **asdict(case),
            "output": str(output.relative_to(ROOT)),
            "command": command,
        }
        if args.resume and (output / "result.json").exists():
            row["status"] = "skipped-existing"
        elif args.dry_run:
            row["status"] = "dry-run"
            print(" ".join(command))
        else:
            pending.append((row, command))
            continue
        ledger.append(row)
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {
            executor.submit(subprocess.run, command, cwd=ROOT, check=False): row
            for row, command in pending
        }
        for future in as_completed(futures):
            row = futures[future]
            completed = future.result()
            row["status"] = "ok" if completed.returncode == 0 else "failed"
            row["returncode"] = completed.returncode
            ledger.append(row)
            (output_root / "ledger.json").write_text(
                json.dumps(ledger, indent=2) + "\n"
            )
            if completed.returncode:
                raise SystemExit(completed.returncode)
    (output_root / "ledger.json").write_text(json.dumps(ledger, indent=2) + "\n")
    blocked = {}
    (output_root / "blocked.json").write_text(json.dumps(blocked, indent=2) + "\n")


if __name__ == "__main__":
    main()
