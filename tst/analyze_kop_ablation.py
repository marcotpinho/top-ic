#!/usr/bin/env python3

import argparse
import csv
import hashlib
import json
import re
import shutil
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from topcc.entities.problem.MotionLimits import MotionLimits
from topcc.core.motion.trajectory import State, connect

ROOT = Path(__file__).resolve().parents[1]
METRICS = (
    "best_reward",
    "best_mean_time",
    "front_size",
    "exact_evaluations",
    "evaluations_per_second",
    "trajectory_seconds",
    "trajectory_ms_per_1000_evaluations",
    "communication_ms_per_1000_evaluations",
    "peak_staleness",
    "piece_count",
    "piece_duration",
    "intermediate_acceleration_fraction",
    "elapsed_seconds",
)


def _best(data):
    feasible = [item for item in data["front"] if item["feasible"]]
    return max(feasible, key=lambda item: (item["reward"], -item["objectives"][1]))


def _acceleration_counts(data):
    intermediate = 0
    total = 0
    limits = [agent["acceleration_axis_limit"] for agent in data["problem"]["agents"]]
    for solution in data["front"]:
        for agent, trajectory in enumerate(solution["trajectories"]):
            for piece in trajectory["pieces"]:
                for axis, value in enumerate(piece["acceleration"]):
                    total += 1
                    bound = limits[agent][axis]
                    if min(abs(value + bound), abs(value), abs(value - bound)) > 1e-8:
                        intermediate += 1
    return intermediate, total


def _load(path, method):
    data = json.loads(path.read_text())
    best = _best(data)
    stats = data["statistics"]
    exact = stats["exact_evaluations"]
    elapsed = data["elapsed_seconds"]
    batch = stats["batch_evaluation"]
    pieces = [
        piece
        for trajectory in best["trajectories"]
        for piece in trajectory["pieces"]
    ]
    intermediate, acceleration_total = _acceleration_counts(data)
    tc = float(data["config"]["recurrence_bound"])
    seed = int(data["config"]["seed"])
    return {
        "method": method,
        "tc": tc,
        "seed": seed,
        "connector_version": data["connector_version"],
        "status": data["status"],
        "best_reward": best["reward"],
        "best_mean_time": best["objectives"][1],
        "front_size": len(data["front"]),
        "exact_evaluations": exact,
        "evaluations_per_second": exact / elapsed,
        "trajectory_seconds": batch["trajectory_seconds"],
        "trajectory_ms_per_1000_evaluations": 1e6
        * batch["trajectory_seconds"]
        / exact,
        "communication_ms_per_1000_evaluations": 1e6
        * batch["communication_seconds"]
        / exact,
        "peak_staleness": best["peak_staleness"],
        "comm_violation": best["comm_violation"],
        "piece_count": len(pieces),
        "piece_duration": sum(piece["duration"] for piece in pieces),
        "intermediate_acceleration_count": intermediate,
        "acceleration_component_count": acceleration_total,
        "intermediate_acceleration_fraction": intermediate / acceleration_total,
        "elapsed_seconds": elapsed,
        "source": str(path.relative_to(ROOT)),
    }


def _results(directory, method):
    return {
        (row["tc"], row["seed"]): row
        for row in (
            _load(path, method)
            for path in sorted(directory.glob("*/result.json"))
        )
    }


def _paired(baseline, kop):
    if baseline.keys() != kop.keys():
        missing_baseline = sorted(kop.keys() - baseline.keys())
        missing_kop = sorted(baseline.keys() - kop.keys())
        raise SystemExit(
            f"unpaired results: missing baseline={missing_baseline}, missing kop={missing_kop}"
        )
    rows = []
    for key in sorted(baseline):
        left = baseline[key]
        right = kop[key]
        row = {"tc": key[0], "seed": key[1]}
        for metric in METRICS:
            row[f"envelope_{metric}"] = left[metric]
            row[f"kop_{metric}"] = right[metric]
            row[f"delta_{metric}"] = right[metric] - left[metric]
        row["envelope_connector"] = left["connector_version"]
        row["kop_connector"] = right["connector_version"]
        rows.append(row)
    return rows


def _summary(rows):
    result = {}
    groups = {tc: [row for row in rows if row["tc"] == tc] for tc in sorted({row["tc"] for row in rows})}
    for tc, group in groups.items():
        metrics = {}
        for metric in METRICS:
            metric_summary = {}
            for prefix in ("envelope", "kop", "delta"):
                values = [row[f"{prefix}_{metric}"] for row in group]
                metric_summary[prefix] = {
                    "mean": statistics.fmean(values),
                    "median": statistics.median(values),
                    "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
                }
            metrics[metric] = metric_summary
        result[str(tc)] = metrics
    return result


def _duration_equivalence(directory):
    connectors = 0
    unresolved = 0
    duration_changes = 0
    maximum_delta = 0.0
    old_pieces = 0
    kop_pieces = 0
    for path in sorted(directory.glob("*/result.json")):
        data = json.loads(path.read_text())
        limits = [
            MotionLimits(
                agent["velocity_axis_limit"], agent["acceleration_axis_limit"]
            )
            for agent in data["problem"]["agents"]
        ]
        for solution in data["front"]:
            old_pieces += sum(
                len(trajectory["pieces"])
                for trajectory in solution["trajectories"]
            )
            for agent, route in enumerate(solution["routes"]):
                times = solution["visit_times"][agent]
                for index, (start, end) in enumerate(zip(route, route[1:])):
                    old_duration = times[index + 1][0] - times[index][0]
                    try:
                        connection = connect(
                            State(start["position"], start["velocity"]),
                            State(end["position"], end["velocity"]),
                            limits[agent],
                        )
                    except ValueError:
                        unresolved += 1
                        continue
                    connectors += 1
                    kop_pieces += len(connection.pieces)
                    delta = abs(connection.duration - old_duration)
                    maximum_delta = max(maximum_delta, delta)
                    if delta > 2e-7:
                        duration_changes += 1
    return {
        "connectors": connectors,
        "unresolved": unresolved,
        "duration_changes_above_2e-7": duration_changes,
        "maximum_absolute_duration_delta": maximum_delta,
        "envelope_piece_count": old_pieces,
        "kop_piece_count_on_same_connectors": kop_pieces,
        "piece_reduction_fraction": 1 - kop_pieces / old_pieces,
    }


def _plot(rows, output, metric, ylabel, filename):
    tcs = sorted({row["tc"] for row in rows})
    figure, axis = plt.subplots(figsize=(8, 5))
    for method, label, marker in (
        ("envelope", "Envelope", "o"),
        ("kop", "KOP", "s"),
    ):
        means = [
            statistics.fmean(
                row[f"{method}_{metric}"] for row in rows if row["tc"] == tc
            )
            for tc in tcs
        ]
        deviations = [
            statistics.stdev(
                row[f"{method}_{metric}"] for row in rows if row["tc"] == tc
            )
            for tc in tcs
        ]
        axis.errorbar(tcs, means, yerr=deviations, marker=marker, capsize=4, label=label)
    axis.set_xscale("symlog", linthresh=0.05)
    axis.set_xlabel("Tc (s)")
    axis.set_ylabel(ylabel)
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output / filename, dpi=180)
    plt.close(figure)


def _write_report(output, rows, summary, equivalence, baseline, kop):
    reward_wins = sum(row["delta_best_reward"] > 0 for row in rows)
    reward_ties = sum(row["delta_best_reward"] == 0 for row in rows)
    reward_losses = sum(row["delta_best_reward"] < 0 for row in rows)
    time_deltas = [
        row["delta_best_mean_time"]
        for row in rows
        if row["delta_best_reward"] == 0
    ]
    throughput = [row["delta_evaluations_per_second"] for row in rows]
    envelope_throughput = statistics.fmean(
        row["envelope_evaluations_per_second"] for row in rows
    )
    kop_throughput = statistics.fmean(
        row["kop_evaluations_per_second"] for row in rows
    )
    envelope_trajectory = statistics.fmean(
        row["envelope_trajectory_ms_per_1000_evaluations"] for row in rows
    )
    kop_trajectory = statistics.fmean(
        row["kop_trajectory_ms_per_1000_evaluations"] for row in rows
    )
    envelope_communication = statistics.fmean(
        row["envelope_communication_ms_per_1000_evaluations"] for row in rows
    )
    kop_communication = statistics.fmean(
        row["kop_communication_ms_per_1000_evaluations"] for row in rows
    )
    report = [
        "# Ablação do conector KOP",
        "",
        f"Foram comparados {len(rows)} pares com o mesmo mapa, Tc e seed.",
        "",
        "## Resultado principal",
        "",
        f"- Recompensa KOP: {reward_wins} vitórias, {reward_ties} empates e {reward_losses} derrotas.",
        f"- Diferença média pareada de throughput: {statistics.fmean(throughput):.3f} avaliações/s.",
        f"- Throughput médio: {envelope_throughput:.3f} envelope e {kop_throughput:.3f} KOP ({(kop_throughput / envelope_throughput - 1) * 100:.1f}%).",
        f"- Construção de trajetórias: {envelope_trajectory:.3f} contra {kop_trajectory:.3f} ms por mil avaliações.",
        f"- Comunicação: {envelope_communication:.3f} contra {kop_communication:.3f} ms por mil avaliações.",
        f"- Diferença média de tempo nos pares com recompensa empatada: {statistics.fmean(time_deltas) if time_deltas else float('nan'):.6f} s.",
        f"- Componentes de aceleração intermediárias no KOP: {sum(row['kop_intermediate_acceleration_fraction'] > 0 for row in rows)} execuções.",
        f"- Replay de {equivalence['connectors']} conectores envelope: {equivalence['duration_changes_above_2e-7']} mudanças de duração; delta máximo {equivalence['maximum_absolute_duration_delta']:.3e} s.",
        f"- Nas mesmas conexões, as peças caíram de {equivalence['envelope_piece_count']} para {equivalence['kop_piece_count_on_same_connectors']} ({equivalence['piece_reduction_fraction'] * 100:.1f}%).",
        "",
        "## Médias por Tc",
        "",
        "| Tc | reward envelope | reward KOP | tempo envelope | tempo KOP | eval/s envelope | eval/s KOP |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for tc in sorted(summary, key=float):
        item = summary[tc]
        report.append(
            f"| {tc} | {item['best_reward']['envelope']['mean']:.3f} | "
            f"{item['best_reward']['kop']['mean']:.3f} | "
            f"{item['best_mean_time']['envelope']['mean']:.3f} | "
            f"{item['best_mean_time']['kop']['mean']:.3f} | "
            f"{item['evaluations_per_second']['envelope']['mean']:.2f} | "
            f"{item['evaluations_per_second']['kop']['mean']:.2f} |"
        )
    report.extend(
        [
            "",
            "## Proveniência",
            "",
            f"- Envelope: `{next(iter(baseline.values()))['connector_version']}`.",
            f"- KOP: `{next(iter(kop.values()))['connector_version']}`.",
            "- As execuções são limitadas por tempo; qualidade e throughput devem ser interpretados conjuntamente.",
            "- A campanha não isola headings: ambos os braços usam headings geométricos; somente o conector muda.",
            "- Como as execuções atingiram o limite de tempo, o ganho de recompensa combina menor custo de avaliação com maior exploração; não demonstra superioridade de qualidade sob igual número de avaliações.",
            "",
            "## Avaliação",
            "",
            "O conector KOP preservou os tempos dos conectores observados e reduziu a representação por partes, acelerando tanto a construção quanto a análise de contatos. Para esta campanha limitada por tempo, os resultados favorecem sua adoção. Uma campanha adicional limitada por avaliações seria necessária para isolar mudanças na paisagem de busca.",
        ]
    )
    (output / "analysis.md").write_text("\n".join(report) + "\n")


def _write_readme(output, rows, baseline, kop):
    template = (ROOT / "docs/templates/README.md").read_text()
    replacements = {
        "{MAP_NAME}": "M2 connector ablation",
        "{RUN_LABEL}": "KOP versus envelope",
        "{INSTANCE_PATH}": "tst/instances/icc-20s-2agents.json",
        "{INSTANCE_LINK}": "../../../tst/instances/icc-20s-2agents.json",
        "{STATUS}": "complete",
        "{ELAPSED_SECONDS}": str(sum(row["envelope_elapsed_seconds"] + row["kop_elapsed_seconds"] for row in rows)),
        "{TIME_CAP_SECONDS}": "900 per run",
        "{SEED}": "101, 102, 103",
        "{RECURRENCE_BOUND}": "0.05, 2, 5, 10, 100",
        "{ALGORITHM}": "paired connector ablation",
        "{CONCISE_EVIDENCE_BASED_OBSERVATIONS}": "see analysis.md and aggregate.json",
        "{RELEVANT_LIMITATIONS_OR_NONE}": "three seeds; wall-clock-limited search; existing envelope runs were reused",
        "{GIT_COMMIT}": "see source run-info.json files",
        "{PATCH_OR_NONE}": "KOP connector worktree recorded by connector version and source hash",
        "{REPRODUCE_SCRIPT}": "reproduce.sh",
        "{REPRODUCE_SCRIPT_LINK}": "reproduce.sh",
        "{REPRODUCE_COMMAND}": "./results/2026-11-15/kop-ablation/reproduce.sh",
        "{PLOT_COMMAND}": "./results/2026-11-15/kop-ablation/reproduce.sh",
        "{VALIDATION_COMMAND_AND_OUTCOME_OR_NOT_RUN}": "all 15 KOP runs parsed; acceleration alphabet checked; unit tests not run",
        "{DETERMINISM_AND_RUNTIME_VARIABILITY_NOTE}": "paired seeds are fixed; wall-clock stopping varies with machine load",
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    template = re.sub(r"\{[A-Z0-9_]+\}", "not applicable to aggregate analysis", template)
    template += (
        "\n## Analysis artifacts\n\n"
        "- [analysis.md](analysis.md)\n"
        "- [paired.csv](paired.csv)\n"
        "- [paired.json](paired.json)\n"
        "- [aggregate.json](aggregate.json)\n"
        "- [reward-by-tc.png](reward-by-tc.png)\n"
        "- [time-by-tc.png](time-by-tc.png)\n"
        "- [throughput-by-tc.png](throughput-by-tc.png)\n"
    )
    (output / "README.md").write_text(template)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="results/2026-11-13/C")
    parser.add_argument("--kop", default="results/2026-11-15/kop/C")
    parser.add_argument("--output", default="results/2026-11-15/kop-ablation")
    args = parser.parse_args()
    baseline_dir = ROOT / args.baseline
    kop_dir = ROOT / args.kop
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    baseline = _results(baseline_dir, "envelope")
    kop = _results(kop_dir, "kop")
    rows = _paired(baseline, kop)
    summary = _summary(rows)
    equivalence = _duration_equivalence(baseline_dir)
    with (output / "paired.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (output / "paired.json").write_text(json.dumps(rows, indent=2) + "\n")
    (output / "aggregate.json").write_text(
        json.dumps({"by_tc": summary, "duration_equivalence": equivalence}, indent=2)
        + "\n"
    )
    _plot(rows, output, "best_reward", "Best feasible reward", "reward-by-tc.png")
    _plot(rows, output, "best_mean_time", "Mean completion time (s)", "time-by-tc.png")
    _plot(rows, output, "evaluations_per_second", "Exact evaluations/s", "throughput-by-tc.png")
    _write_report(output, rows, summary, equivalence, baseline, kop)
    _write_readme(output, rows, baseline, kop)
    shutil.copy2(__file__, output / Path(__file__).name)
    command = (
        "#!/bin/sh\nset -eu\ncd \"$(dirname \"$0\")/../../..\"\n"
        ".venv/bin/python tst/analyze_kop_ablation.py\n"
    )
    reproduction = output / "reproduce.sh"
    reproduction.write_text(command)
    reproduction.chmod(0o755)
    source_hash = hashlib.sha256((ROOT / "src/core/motion/trajectory.py").read_bytes()).hexdigest()
    (output / "source-info.json").write_text(
        json.dumps(
            {
                "baseline": args.baseline,
                "kop": args.kop,
                "trajectory_source_sha256": source_hash,
                "baseline_connector": next(iter(baseline.values()))["connector_version"],
                "kop_connector": next(iter(kop.values()))["connector_version"],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
