"""Run one analytical suite and save a reproducible result bundle."""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "A": ROOT / "tst/verify_contacts.py",
    "B": ROOT / "tst/verify_propagation.py",
    "F": ROOT / "tst/verify_batch.py",
    "G": ROOT / "tst/verify_properties.py",
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=tuple(SCRIPTS), required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.arguments and args.arguments[0] == "--":
        args.arguments = args.arguments[1:]
    return args


def readme(suite, output, elapsed, command, status):
    template = (ROOT / "docs/templates/README.md").read_text()
    relative = output.relative_to(ROOT)
    reproduction = f"./{relative.as_posix()}/reproduce.sh"
    values = {
        "MAP_NAME": f"analytical-suite-{suite}",
        "RUN_LABEL": output.name,
        "STATUS": status,
        "ELAPSED_SECONDS": f"{elapsed:.6f}",
        "TIME_CAP_SECONDS": "not applicable",
        "RESULT_JSON": "report.json",
        "RESULT_JSON_LINK": "report.json",
        "REPRODUCE_SCRIPT": "reproduce.sh",
        "REPRODUCE_SCRIPT_LINK": "reproduce.sh",
        "REPRODUCE_COMMAND": reproduction,
        "PLOT_COMMAND": "not applicable",
        "VALIDATION_COMMAND_AND_OUTCOME_OR_NOT_RUN": f"analytical suite {suite}: {status}",
        "GIT_COMMIT": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip(),
        "PYTHON_VERSION": sys.version.split()[0],
        "DEPENDENCY_SOURCE_OR_LOCKFILE": "current .venv and pyproject.toml",
        "OPERATING_SYSTEM": sys.platform,
        "PATCH_OR_NONE": "current working tree",
        "REPRODUCTION_NOTE": "analytical checks are deterministic",
    }
    for key, value in values.items():
        template = template.replace(f"{{{key}}}", str(value))
    template = re.sub(r"\{[A-Z0-9_]+\}", "not applicable", template)
    lines = []
    for line in template.splitlines():
        if line.startswith("- **Artifacts:**"):
            line = "- **Artifacts:** [report.json](report.json); [run.log](run.log); [run-info.json](run-info.json); [reproduce.sh](reproduce.sh)."
        lines.append(line)
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    output = (ROOT / args.output_dir).resolve()
    results = (ROOT / "results").resolve()
    if not output.is_relative_to(results) or output == results:
        raise SystemExit("--output-dir must be below results/")
    output.mkdir(parents=True, exist_ok=True)
    command = [
        str(ROOT / ".venv/bin/python"),
        str(SCRIPTS[args.suite]),
        *args.arguments,
    ]
    reproduce = [
        ".venv/bin/python",
        "tst/run_verification.py",
        "--suite",
        args.suite,
        "--output-dir",
        str(output.relative_to(ROOT)),
    ]
    if args.arguments:
        reproduce.extend(("--", *args.arguments))
    root_relative = os.path.relpath(ROOT, output)
    script = (
        f'#!/bin/sh\nset -eu\ncd "$(dirname "$0")/{root_relative}"\n'
        + shlex.join(reproduce)
        + "\n"
    )
    (output / "reproduce.sh").write_text(script)
    (output / "reproduce.sh").chmod(0o755)
    started_utc = datetime.now(UTC).isoformat()
    started = perf_counter()
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    elapsed = perf_counter() - started
    (output / "run.log").write_text(completed.stdout + completed.stderr)
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError:
        report = {
            "schema_version": 1,
            "suite": args.suite,
            "status": "failed",
            "returncode": completed.returncode,
        }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    status = (
        "ok" if completed.returncode == 0 and report.get("status") == "ok" else "failed"
    )
    run_info = {
        "schema_version": 1,
        "suite": args.suite,
        "status": status,
        "returncode": completed.returncode,
        "started_utc": started_utc,
        "finished_utc": datetime.now(UTC).isoformat(),
        "elapsed_seconds": elapsed,
        "command": command,
    }
    (output / "run-info.json").write_text(json.dumps(run_info, indent=2) + "\n")
    (output / "README.md").write_text(
        readme(args.suite, output, elapsed, command, status)
    )
    print(json.dumps(run_info, indent=2))
    if status != "ok":
        raise SystemExit(completed.returncode or 1)


if __name__ == "__main__":
    main()
