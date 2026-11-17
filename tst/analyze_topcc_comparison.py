"""Summarize the matched TOP-CC and TOP-ICC constant-connectivity campaign."""

from argparse import ArgumentParser
import csv
import json
from pathlib import Path


MAPS = (
    ("post-disaster", "Post-disaster"),
    ("wildfire", "Wildfire"),
    ("pipeline", "Pipeline"),
    ("agriculture", "Agriculture"),
)


def _load(path):
    return json.loads(path.read_text())


def _topicc_best(result):
    feasible = [solution for solution in result["front"] if solution["feasible"]]
    return min(feasible, key=lambda solution: (-solution["reward"], solution["objectives"][1]))


def _topcc_budget_best(result):
    valid = [solution for solution in result["solutions"] if solution["budget_valid"]]
    return min(valid, key=lambda solution: (-solution["reward"], solution["mean_completion_time"]))


def _rows(root, topcc_subdir):
    rows = []
    for folder, label in MAPS:
        topcc = _load(root / folder / topcc_subdir / "result.json")
        topicc = _load(root / folder / "top-icc/result.json")
        budget = _topcc_budget_best(topcc)
        connected = topcc["best_connected"]
        icc = _topicc_best(topicc)
        total_reward = sum(task["reward"] for task in topicc["problem"]["tasks"])
        rows.append(
            {
                "map": label,
                "total_reward": total_reward,
                "topcc_connected_found": connected is not None,
                "topcc_connected_reward": connected["reward"] if connected else None,
                "topcc_connected_mean_time": connected["mean_completion_time"] if connected else None,
                "topcc_budget_only_reward": budget["reward"],
                "topcc_budget_only_mean_time": budget["mean_completion_time"],
                "topcc_evaluations": topcc["statistics"]["evaluations"],
                "topicc_reward": icc["reward"],
                "topicc_mean_time": icc["objectives"][1],
                "topicc_peak_staleness": icc["peak_staleness"],
                "topicc_evaluations": topicc["statistics"]["exact_evaluations"],
            }
        )
    return rows


def _value(value, digits=2):
    return "---" if value is None else f"{value:.{digits}f}"


def _analysis(rows, fair):
    protocol = (
        "TOP-CC-C0 used `multi_vis` and a deterministic budget-valid connected convoy seed before the original MOVNS. Its agriculture alarm was armed 10 seconds early to absorb an uninterruptible Numba batch and stopped after 591.57 seconds."
        if fair
        else "TOP-CC used its original RSSI multiobjective search."
    )
    lines = [
        f"# {'TOP-CC-C0' if fair else 'TOP-CC'} versus TOP-ICC at constant connectivity",
        "",
        f"All searches used seed 42 and a nominal 600-second wall-clock budget. TOP-ICC used exact `Tc=0`. {protocol} The saved TOP-CC archive was post-filtered by the source time budgets converted to distance at 3 m/s and by exact continuous connectivity of the piecewise-linear paths.",
        "",
        "| Map | Available reward | TOP-CC connected reward | TOP-CC connected mean time (s) | TOP-ICC reward | TOP-ICC mean time (s) | TOP-ICC peak staleness (s) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {map} | {total_reward:g} | {cc_reward} | {cc_time} | {icc_reward:g} | {icc_time:.2f} | {delta:.2e} |".format(
                map=row["map"],
                total_reward=row["total_reward"],
                cc_reward=_value(row["topcc_connected_reward"]),
                cc_time=_value(row["topcc_connected_mean_time"]),
                icc_reward=row["topicc_reward"],
                icc_time=row["topicc_mean_time"],
                delta=row["topicc_peak_staleness"],
            )
        )
    lines.extend(
        [
            "",
            "## Diagnostic without constant connectivity",
            "",
            "| Map | TOP-CC budget-valid reward | Mean time (s) | TOP-CC evaluations | TOP-ICC evaluations |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['map']} | {row['topcc_budget_only_reward']:g} | {row['topcc_budget_only_mean_time']:.2f} | {row['topcc_evaluations']} | {row['topicc_evaluations']} |"
        )
    lines.append("")
    if fair:
        lines.append(
            "TOP-CC-C0 retained at least one continuously connected, budget-valid solution on every map. TOP-ICC also returned connected solutions on every map. The connected reward comparison is therefore defined for all four pairs."
        )
    else:
        lines.append(
            "TOP-CC saved no continuously connected, budget-valid solution on any of the four maps. This is a search outcome, not a proof of infeasibility."
        )
    lines.extend(
        [
            "",
            "Because TOP-CC uses constant-speed linear motion while TOP-ICC uses acceleration-bounded double-integrator motion, completion times describe each model's own solution and should not be read as a controlled kinematic speed comparison.",
            "",
            "The campaign has one seed. It supports an observed-result comparison at the fixed budget, not a statistical performance claim.",
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    parser = ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--topcc-subdir", default="top-cc")
    parser.add_argument("--fair", action="store_true")
    arguments = parser.parse_args()
    rows = _rows(arguments.root, arguments.topcc_subdir)
    with (arguments.root / "comparison.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (arguments.root / "analysis.md").write_text(_analysis(rows, arguments.fair))


if __name__ == "__main__":
    main()
