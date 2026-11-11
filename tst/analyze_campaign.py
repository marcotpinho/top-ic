"""Parse campaign bundles and produce descriptive and inferential summaries."""

import argparse
import json
import re
from collections import defaultdict
from itertools import pairwise
from pathlib import Path

import numpy as np
from scipy.stats import kruskal, mannwhitneyu, wilcoxon

ROOT = Path(__file__).resolve().parents[1]


def holm(rows):
    ordered = sorted(enumerate(rows), key=lambda item: item[1]["p"])
    adjusted = [1.0] * len(rows)
    running = 0.0
    total = len(rows)
    for rank, (index, row) in enumerate(ordered):
        running = max(running, min(1.0, (total - rank) * row["p"]))
        adjusted[index] = running
    return [{**row, "p_holm": adjusted[index]} for index, row in enumerate(rows)]


def case_label(name):
    return re.sub(r"-s\d+$", "", name)


def load_rows(campaign_root):
    ledger = json.loads((campaign_root / "ledger.json").read_text())
    rows = []
    for item in ledger:
        result_path = ROOT / item["output"] / "result.json"
        if not result_path.exists():
            continue
        data = json.loads(result_path.read_text())
        front = data["front"]
        best = max(
            front, key=lambda row: (row["reward"], -row["objectives"][1]), default=None
        )
        stats = data["statistics"]
        rows.append(
            {
                "group": item["group"],
                "case": case_label(item["name"]),
                "name": item["name"],
                "seed": item["seed"],
                "status": data["status"],
                "reward": stats["maximum_reward"],
                "hypervolume": stats["archive_hypervolume"],
                "front_size": len(front),
                "delta": best["peak_staleness"] if best else None,
                "elapsed_seconds": data["elapsed_seconds"],
                "exact_evaluations": stats.get("exact_evaluations", 0),
                "repair_calls": stats.get("communication_repair_calls", 0),
                "repair_zeroed": stats.get("communication_repair_zeroed", 0),
                "pool_base_fraction": stats.get("pool_base_fraction", 0.0),
                "result_path": str(result_path.relative_to(ROOT)),
            }
        )
    return rows


def descriptive(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["group"], row["case"])].append(row)
    output = []
    for (group, case), values in sorted(grouped.items()):
        record = {"group": group, "case": case, "runs": len(values)}
        for metric in (
            "reward",
            "hypervolume",
            "front_size",
            "delta",
            "elapsed_seconds",
        ):
            sample = np.asarray(
                [row[metric] for row in values if row[metric] is not None], dtype=float
            )
            record[metric] = {
                "median": float(np.median(sample)) if sample.size else None,
                "q1": float(np.percentile(sample, 25)) if sample.size else None,
                "q3": float(np.percentile(sample, 75)) if sample.size else None,
            }
        output.append(record)
    return output


def inferential(rows):
    output = {"C": [], "D": [], "E": []}
    by_case = defaultdict(list)
    for row in rows:
        by_case[(row["group"], row["case"])].append(row)
    for map_name in ("m2", "m3"):
        labels = [f"{map_name}-tc{value}" for value in ("0p05", "2", "5", "10", "100")]
        comparisons = []
        for low, high in pairwise(labels):
            for metric in ("reward", "hypervolume"):
                left = {row["seed"]: row[metric] for row in by_case[("C", low)]}
                right = {row["seed"]: row[metric] for row in by_case[("C", high)]}
                seeds = sorted(left.keys() & right.keys())
                if seeds:
                    test = wilcoxon(
                        [right[seed] for seed in seeds],
                        [left[seed] for seed in seeds],
                        alternative="less",
                        zero_method="zsplit",
                    )
                    comparisons.append(
                        {
                            "map": map_name,
                            "low": low,
                            "high": high,
                            "metric": metric,
                            "p": float(test.pvalue),
                        }
                    )
        output["C"].extend(holm(comparisons))
    factors = defaultdict(dict)
    for (group, case), values in by_case.items():
        if group != "D":
            continue
        factor, level = case.split("-", 1)
        factors[factor][level] = values
    for factor, levels in sorted(factors.items()):
        for metric in ("reward", "hypervolume"):
            samples = [[row[metric] for row in values] for values in levels.values()]
            if len(samples) >= 3 and all(samples):
                test = kruskal(*samples)
                output["D"].append(
                    {
                        "factor": factor,
                        "metric": metric,
                        "test": "kruskal",
                        "p": float(test.pvalue),
                    }
                )
            pairs = []
            names = sorted(levels)
            for left_index, left in enumerate(names):
                for right in names[left_index + 1 :]:
                    if levels[left] and levels[right]:
                        test = mannwhitneyu(
                            [row[metric] for row in levels[left]],
                            [row[metric] for row in levels[right]],
                            alternative="two-sided",
                        )
                        pairs.append(
                            {
                                "factor": factor,
                                "left": left,
                                "right": right,
                                "metric": metric,
                                "p": float(test.pvalue),
                            }
                        )
            output["D"].extend(holm(pairs))
    for map_name in ("m2", "m3"):
        baseline = {row["seed"]: row for row in by_case[("E", f"{map_name}-E0-base")]}
        comparisons = []
        for (group, case), values in by_case.items():
            if (
                group != "E"
                or not case.startswith(f"{map_name}-")
                or case.endswith("E0-base")
            ):
                continue
            variation = {row["seed"]: row for row in values}
            seeds = sorted(baseline.keys() & variation.keys())
            for metric in ("reward", "hypervolume"):
                if seeds:
                    test = wilcoxon(
                        [variation[seed][metric] for seed in seeds],
                        [baseline[seed][metric] for seed in seeds],
                        alternative="two-sided",
                        zero_method="zsplit",
                    )
                    comparisons.append(
                        {
                            "map": map_name,
                            "case": case,
                            "metric": metric,
                            "p": float(test.pvalue),
                        }
                    )
        output["E"].extend(holm(comparisons))
    return output


def acceptance(rows):
    output = {}
    for map_name in ("m2", "m3"):
        near_zero = [
            row
            for row in rows
            if row["group"] == "C" and row["case"] == f"{map_name}-tc0p05"
        ]
        output[f"C1-{map_name}"] = {
            "runs": len(near_zero),
            "nonempty_and_delta_within_tc": sum(
                row["front_size"] > 0
                and row["delta"] is not None
                and row["delta"] <= 0.05
                for row in near_zero
            ),
            "required": 8 if len(near_zero) >= 10 else None,
        }
        middle = [
            row
            for row in rows
            if row["group"] == "C" and row["case"] == f"{map_name}-tc5"
        ]
        output[f"C2-{map_name}"] = {
            "runs": len(middle),
            "nonempty": sum(row["front_size"] > 0 for row in middle),
        }
        inactive = [
            row
            for row in rows
            if row["group"] == "C" and row["case"] == f"{map_name}-tc100"
        ]
        output[f"C3-{map_name}"] = {
            "runs": len(inactive),
            "fronts_nonempty": sum(row["front_size"] > 0 for row in inactive),
        }
    reprojection_failures = []
    reprojection_count = 0
    for row in rows:
        if row["group"] != "C" or not row["case"].endswith("-tc2"):
            continue
        data = json.loads((ROOT / row["result_path"]).read_text())
        for solution_index, solution in enumerate(data["front"]):
            peaks = solution["communication"]["pair_peaks"]
            projected_cv = sum(
                max(0.0, value - 5.0)
                for receiver, values in enumerate(peaks)
                for source, value in enumerate(values)
                if receiver != source
            )
            reprojection_count += 1
            if solution["peak_staleness"] <= 5.0 and projected_cv != 0:
                reprojection_failures.append(
                    {"result": row["result_path"], "solution": solution_index}
                )
    output["C4-reprojection"] = {
        "solutions": reprojection_count,
        "failures": reprojection_failures,
    }
    incremental = [
        row
        for row in rows
        if row["group"] == "E" and row["case"].endswith("E10-verify-incremental")
    ]
    output["E10-incremental"] = {
        "runs": len(incremental),
        "divergences": sum(
            json.loads((ROOT / row["result_path"]).read_text())["statistics"][
                "incremental_evaluation"
            ].get("oracle_divergences", 0)
            for row in incremental
        ),
    }
    return output


def markdown(summary):
    lines = [
        "# TOP-ICC test-plan campaign summary",
        "",
        "| Group | Case | Runs | Reward median [IQR] | HV median [IQR] |",
        "|---|---|---:|---:|---:|",
    ]
    for row in summary["descriptive"]:
        reward = row["reward"]
        hypervolume = row["hypervolume"]
        lines.append(
            f"| {row['group']} | {row['case']} | {row['runs']} | "
            f"{reward['median']} [{reward['q1']}, {reward['q3']}] | "
            f"{hypervolume['median']} [{hypervolume['q1']}, {hypervolume['q3']}] |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign_root")
    args = parser.parse_args()
    root = (ROOT / args.campaign_root).resolve()
    rows = load_rows(root)
    summary = {
        "schema_version": 1,
        "runs": len(rows),
        "descriptive": descriptive(rows),
        "inferential": inferential(rows),
        "acceptance": acceptance(rows),
    }
    (root / "analysis.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )
    (root / "analysis.md").write_text(markdown(summary))
    print(
        json.dumps(
            {
                "runs": len(rows),
                "analysis": str((root / "analysis.json").relative_to(ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
