"""Run one TOP-ICC experiment and save its complete reproducibility bundle."""

import argparse
import hashlib
import json
import os
import platform
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]


def _parse_arguments() -> tuple[Path, list[str]]:
    """Parse the output folder and preserve remaining arguments for topcc."""
    parser = argparse.ArgumentParser(
        description=(
            "Run a TOP-ICC search, generate plots, and save reproduction artifacts. "
            "Pass topcc options after --."
        )
    )
    parser.add_argument(
        "--output-dir", required=True, help="destination under results/"
    )
    arguments, topcc_arguments = parser.parse_known_args()
    if topcc_arguments and topcc_arguments[0] == "--":
        topcc_arguments = topcc_arguments[1:]
    return Path(arguments.output_dir), topcc_arguments


def _relative_to_root(path: Path) -> str:
    """Return a repository relative path for generated commands and metadata."""
    return path.resolve().relative_to(ROOT).as_posix()


def _reproduction_script(output_dir: Path, arguments: list[str]) -> str:
    """Build a shell script that repeats this run with the same arguments."""
    root_relative = os.path.relpath(ROOT, output_dir)
    command = [
        ".venv/bin/python",
        "scripts/run_experiment.py",
        "--output-dir",
        _relative_to_root(output_dir),
        "--",
        *arguments,
    ]
    return (
        "#!/bin/sh\nset -eu\n"
        f'cd "$(dirname "$0")/{root_relative}"\n' + shlex.join(command) + "\n"
    )


def _git_revision() -> str | None:
    """Return the current Git revision when this checkout has Git metadata."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _instance_hash(arguments: list[str]) -> dict[str, str] | None:
    """Hash the selected instance file when the CLI arguments name one."""
    try:
        index = arguments.index("--instance")
        instance_path = Path(arguments[index + 1])
    except (ValueError, IndexError):
        return None
    if not instance_path.is_absolute():
        instance_path = ROOT / instance_path
    digest = hashlib.sha256(instance_path.read_bytes()).hexdigest()
    return {"path": os.path.relpath(instance_path, ROOT), "sha256": digest}


def _generate_plots(result_path: Path, output_dir: Path) -> list[str]:
    """Generate standard analysis plots and the best saved Tc-feasible path."""
    from topcc.viz import draw_solution_paths, plot_result

    data = json.loads(result_path.read_text())
    plot_result(data, output_dir)
    recurrence_bound = data["config"]["recurrence_bound"]
    slice_row = next(
        (row for row in data.get("tc_slices", []) if row["tc"] == recurrence_bound),
        None,
    )
    if slice_row is not None and slice_row["front_indices"]:
        best = max(
            (data["front"][index] for index in slice_row["front_indices"]),
            key=lambda solution: (
                solution["reward"],
                -solution["objectives"][1],
            ),
        )
        path = output_dir / "best-path-under-Tc.png"
        draw_solution_paths(
            data["problem"],
            best,
            f"Best archive path satisfying Tc={recurrence_bound:g} s",
            path,
        )
    return sorted(
        path.name
        for path in output_dir.iterdir()
        if path.suffix.lower() in {".png", ".svg", ".pdf"}
    )


def _format(value: object) -> str:
    """Render JSON values compactly for the result README."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ": "))


def _dependency_versions() -> str:
    """Describe the installed numerical and plotting dependencies."""
    packages = []
    for package in ("numpy", "scipy", "matplotlib"):
        try:
            packages.append(f"{package} {version(package)}")
        except PackageNotFoundError:
            packages.append(f"{package} unavailable")
    return ", ".join(packages)


def _instance_replacements(
    problem: dict, run_info: dict, output_dir: Path
) -> dict[str, str]:
    """Describe the instance name, frame, and checksum for the README."""
    positions = [problem["start"], problem["end"]]
    positions.extend(task["position"] for task in problem["tasks"])
    bounds = [
        [
            min(point[axis] for point in positions),
            max(point[axis] for point in positions),
        ]
        for axis in range(2)
    ]
    instance = run_info.get("instance")
    path = instance["path"] if instance else "built-in smoke instance"
    link = os.path.relpath(ROOT / path, output_dir) if instance else "../../README.md"
    return {
        "{MAP_NAME}": str(problem["name"]),
        "{INSTANCE_PATH}": path,
        "{INSTANCE_LINK}": link,
        "{INSTANCE_SHA256}": instance["sha256"] if instance else "built-in",
        "{UNITS}": "meters and seconds",
        "{MAP_BOUNDS_OR_SIZE}": _format({"x": bounds[0], "y": bounds[1]}),
    }


def _problem_replacements(problem: dict) -> dict[str, str]:
    """Describe agents, tasks, motion limits, and model constraints."""
    agents = problem["agents"]
    return {
        "{AGENT_COUNT}": str(len(agents)),
        "{START_POSITIONS}": _format(problem["start"]),
        "{END_POSITIONS}": _format(problem["end"]),
        "{INITIAL_VELOCITIES}": _format(
            [agent["initial_velocity"] for agent in agents]
        ),
        "{VELOCITY_LIMITS}": _format(
            [agent["velocity_axis_limit"] for agent in agents]
        ),
        "{ACCELERATION_LIMITS}": _format(
            [agent["acceleration_axis_limit"] for agent in agents]
        ),
        "{BUDGETS_SECONDS}": _format([agent["time_budget"] for agent in agents]),
        "{TASK_COUNT}": str(len(problem["tasks"])),
        "{TOTAL_REWARD}": _format(sum(task["reward"] for task in problem["tasks"])),
        "{REWARD_RULE}": "rewards are collected by explicit TASK visits",
        "{COLLISION_RULES}": "collisions are ignored",
        "{WAIT_RULES}": "waiting visits are stationary",
        "{OTHER_ASSUMPTIONS}": "continuous box double-integrator motion",
    }


def _search_replacements(config: dict, stats: dict) -> dict[str, str]:
    """Describe the ICC constraints and limits used by this run."""
    passes = {
        name: row["calls"] for name, row in stats["profiling"]["neighborhoods"].items()
    }
    return {
        "{ALGORITHM}": f"{config['mode']} {config['algorithm']}",
        "{SEED}": str(config["seed"]),
        "{TIME_CAP_SECONDS}": _format(config["max_seconds"]),
        "{EVALUATION_CAP}": str(config["max_evaluations"]),
        "{ITERATION_CAP}": str(config["max_iterations"]),
        "{COMMUNICATION_RANGE}": _format(config["comm_range"]),
        "{DISTANCE_UNITS}": "m",
        "{HANDSHAKE_TIME}": _format(config["handshake_time"]),
        "{RECURRENCE_BOUND}": _format(config["recurrence_bound"]),
        "{HV_THRESHOLD}": _format(config["neighborhood_hv_tau"]),
        "{MAX_NEIGHBORHOOD_PASSES}": str(config["neighborhood_max_passes"]),
        "{EPSILON_WIDTHS}": _format(
            {
                "reward": config["eps_reward"],
                "time": config["eps_time"],
                "violation": stats["effective_epsilon"][2],
            }
        ),
        "{HV_REFERENCE_POINT}": _format(stats["hypervolume_reference_point"]),
        "{HV_SCALES}": _format(stats["hypervolume_scales"]),
        "{WAYPOINT_STEPS}": _format(config["waypoint_steps"]),
        "{WAIT_STEPS}": _format(config["wait_steps"]),
        "{MAX_FREE_WAYPOINTS}": str(config["max_free_waypoints"]),
        "{NEIGHBORHOOD_CANDIDATES}": str(config["neighborhood_candidates"]),
        "{DISABLED_NEIGHBORHOODS}": _format(config["disabled"]),
        "{NEIGHBORHOOD_PASS_COUNTS}": _format(passes),
    }


def _outcome_replacements(data: dict) -> dict[str, str]:
    """Summarize the final archive and the best configured-Tc solution."""
    stats = data["statistics"]
    feasible = [
        data["front"][index] for index in data.get("feasible_front_indices", [])
    ]
    best = max(
        feasible,
        key=lambda solution: (solution["reward"], -solution["objectives"][1]),
        default=None,
    )
    return {
        "{STATUS}": data["status"],
        "{ELAPSED_SECONDS}": f"{data['elapsed_seconds']:.3f}",
        "{EVALUATION_COUNT}": str(stats.get("evaluated", 0)),
        "{OUTER_ITERATION_COUNT}": str(stats.get("iterations", 0)),
        "{ARCHIVE_SIZE}": str(len(data["front"])),
        "{TC_FEASIBLE_ARCHIVE_SIZE}": str(len(feasible)),
        "{BEST_FEASIBLE_REWARD}": _format(best["reward"] if best else None),
        "{BEST_FEASIBLE_MEAN_TIME}": _format(best["objectives"][1] if best else None),
        "{BEST_FEASIBLE_DELTA}": _format(best["peak_staleness"] if best else None),
        "{FINAL_HYPERVOLUME}": _format(stats["archive_hypervolume"]),
        "{CONCISE_EVIDENCE_BASED_OBSERVATIONS}": (
            f"The run produced {len(data['front'])} archive solutions, "
            f"{len(feasible)} satisfying Tc, and generated "
            f"{stats.get('neighborhood_execution_count', 0)} neighborhood calls."
        ),
        "{RELEVANT_LIMITATIONS_OR_NONE}": (
            "wall-clock stopping can change the final candidate count under different CPU load"
        ),
    }


def _artifact_replacements() -> dict[str, str]:
    """Link standard artifacts and neighborhood execution history."""
    files = {
        "{RESULT_JSON}": "result.json",
        "{RESULT_JSON_LINK}": "result.json",
        "{BEST_PATH_PLOT}": "best-path-under-Tc.png",
        "{BEST_PATH_LINK}": "best-path-under-Tc.png",
        "{PARETO_PLOT}": "pareto-frontier.png",
        "{PARETO_LINK}": "pareto-frontier.png",
        "{DELTA_PLOT}": "delta-tradeoff.png",
        "{DELTA_LINK}": "delta-tradeoff.png",
        "{PARETO_EVOLUTION_PLOT}": "pareto-evolution.png",
        "{PARETO_EVOLUTION_LINK}": "pareto-evolution.png",
        "{NEIGHBORHOOD_LOG}": "result_neighborhoods.json",
        "{NEIGHBORHOOD_LOG_LINK}": "result_neighborhoods.json",
    }
    return files


def _reproduction_replacements(run_info: dict, output_dir: Path) -> dict[str, str]:
    """Describe the saved reproduction and local runtime environment."""
    command = f"./{_relative_to_root(output_dir)}/reproduce.sh"
    return {
        "{GIT_COMMIT}": run_info.get("repository_revision") or "unknown",
        "{PATCH_OR_NONE}": "working tree state is not embedded in this run",
        "{PYTHON_VERSION}": sys.version.split()[0],
        "{DEPENDENCY_SOURCE_OR_LOCKFILE}": _dependency_versions(),
        "{OPERATING_SYSTEM}": platform.platform(),
        "{REPRODUCE_SCRIPT}": "reproduce.sh",
        "{REPRODUCE_SCRIPT_LINK}": "reproduce.sh",
        "{REPRODUCE_COMMAND}": command,
        "{PLOT_COMMAND}": command,
        "{VALIDATION_COMMAND_AND_OUTCOME_OR_NOT_RUN}": "not run; unit tests are disabled by repository instructions",
        "{DETERMINISM_AND_RUNTIME_VARIABILITY_NOTE}": (
            "the seed fixes search randomness; wall-clock stopping can vary with machine load"
        ),
    }


def _write_readme(output_dir: Path, run_info: dict) -> None:
    """Fill the repository results template with facts from the saved run."""
    data = json.loads((output_dir / "result.json").read_text())
    replacements = {
        "{MAP_NAME}": str(data["problem"]["name"]),
        "{RUN_LABEL}": output_dir.name,
        **_instance_replacements(data["problem"], run_info, output_dir),
        **_problem_replacements(data["problem"]),
        **_search_replacements(data["config"], data["statistics"]),
        **_outcome_replacements(data),
        **_artifact_replacements(),
        **_reproduction_replacements(run_info, output_dir),
    }
    template = (ROOT / "docs/templates/README.md").read_text()
    readme = template
    for placeholder, value in replacements.items():
        readme = readme.replace(placeholder, value)
    artifact_names = [
        "result.json",
        "result_neighborhoods.json",
        "run-info.json",
        "run.log",
        "reproduce.sh",
        *run_info["plot_files"],
    ]
    artifact_links = _artifact_links(output_dir, artifact_names)
    readme = _replace_artifact_line(readme, artifact_links)
    (output_dir / "README.md").write_text(readme)


def _artifact_links(output_dir: Path, names: list[str]) -> str:
    """Return links for the artifacts that were actually generated."""
    return "; ".join(
        f"[{name}]({name})" for name in names if (output_dir / name).exists()
    )


def _replace_artifact_line(readme: str, artifact_links: str) -> str:
    """Replace the template's generic artifact list with saved files."""
    lines = readme.splitlines()
    updated = [
        f"- **Artifacts:** {artifact_links}."
        if line.startswith("- **Artifacts:**")
        else line
        for line in lines
    ]
    return "\n".join(updated) + "\n"


def _validate_output_dir(output_dir: Path) -> None:
    """Require every experiment bundle to be stored below results/."""
    results_dir = (ROOT / "results").resolve()
    if not output_dir.is_relative_to(results_dir) or output_dir == results_dir:
        raise SystemExit("--output-dir must name a subdirectory under results/")


def _execute_search(
    output_dir: Path, arguments: list[str]
) -> tuple[Path, list[str], float]:
    """Save the reproduction command and execute the TOP-ICC CLI."""
    reproduction_path = output_dir / "reproduce.sh"
    reproduction_path.write_text(_reproduction_script(output_dir, arguments))
    reproduction_path.chmod(0o755)
    result_path = output_dir / "result.json"
    command = [
        sys.executable,
        "-m",
        "topcc.main",
        *arguments,
        "--output",
        _relative_to_root(result_path),
    ]
    started = perf_counter()
    process = subprocess.run(
        command,
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    elapsed_seconds = perf_counter() - started
    (output_dir / "run.log").write_text(process.stdout + process.stderr)
    if process.returncode != 0:
        raise SystemExit(
            f"TOP-ICC exited with status {process.returncode}; see "
            f"{_relative_to_root(output_dir / 'run.log')}"
        )
    return result_path, command, elapsed_seconds


def _complete_run(
    output_dir: Path,
    result_path: Path,
    command: list[str],
    elapsed_seconds: float,
    started_utc: str,
) -> dict:
    """Generate plots, metadata, and the completed results README."""
    plot_files = _generate_plots(result_path, output_dir)
    run_info = {
        "schema_version": 1,
        "started_utc": started_utc,
        "finished_utc": datetime.now(UTC).isoformat(),
        "elapsed_seconds": elapsed_seconds,
        "command": command,
        "reproduction_script": "reproduce.sh",
        "repository_revision": _git_revision(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "instance": _instance_hash(command[3:]),
        "result_file": result_path.name,
        "neighborhood_log": result_path.with_name(
            f"{result_path.stem}_neighborhoods.json"
        ).name,
        "plot_files": plot_files,
        "exit_status": 0,
    }
    (output_dir / "run-info.json").write_text(
        json.dumps(run_info, indent=2, allow_nan=False) + "\n"
    )
    _write_readme(output_dir, run_info)
    print(json.dumps(run_info, indent=2))
    return run_info


def _run_experiment(output_dir: Path, arguments: list[str]) -> None:
    """Run the optimizer and assemble its reproducibility bundle."""
    output_dir.mkdir(parents=True, exist_ok=True)
    started_utc = datetime.now(UTC).isoformat()
    result_path, command, elapsed_seconds = _execute_search(output_dir, arguments)
    _complete_run(output_dir, result_path, command, elapsed_seconds, started_utc)


def main() -> int:
    """Run topcc and save results, plots, run information, and reproduction script."""
    output_argument, topcc_arguments = _parse_arguments()
    output_dir = (ROOT / output_argument).resolve()
    _validate_output_dir(output_dir)
    if not topcc_arguments:
        raise SystemExit("Pass topcc parameters after --, for example -- --seed 42")
    _run_experiment(output_dir, topcc_arguments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
