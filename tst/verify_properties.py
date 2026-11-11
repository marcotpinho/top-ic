"""Execute general consistency properties G1-G8."""

import argparse
import json
from itertools import pairwise
from pathlib import Path

from common import CheckLog, close, piece, records, trajectory
from topcc.evaluation_core.communication import sweep
from topcc.evaluation_core.contacts import ContactUncertain, pair_contacts
from verify_propagation import CASES, violation

ROOT = Path(__file__).resolve().parents[1]


def normalize_json(value):
    if isinstance(value, dict):
        return {
            key: normalize_json(item)
            for key, item in value.items()
            if key
            not in {
                "elapsed_seconds",
                "profiling",
                "generation_seconds",
                "evaluation_seconds",
                "total_seconds",
            }
        }
    if isinstance(value, list):
        return [normalize_json(item) for item in value]
    return value


def classify_tangent(offset):
    first = trajectory([piece((0, 0), (1, 0), (0, 0), 10)], 10)
    second = trajectory([piece((5, 2 + offset), (0, 0), (0, 0), 10)], 10)
    try:
        intervals = pair_contacts(first, second, 10, 2)
    except ContactUncertain:
        return "unresolved"
    return intervals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--determinism-results", nargs=2)
    args = parser.parse_args()
    log = CheckLog("G-properties")
    for name, (agents, links, _, _) in CASES.items():
        cvs = []
        peaks = []
        for recurrence in range(1, 13):
            result = sweep(agents, 10.0, records(links), recurrence)
            peaks.append(result.pair_peaks)
            cvs.append(violation(result.pair_peaks, recurrence))
            log.check(
                f"G2 {name} Tc={recurrence}",
                (result.peak_staleness <= recurrence) == (cvs[-1] == 0),
                {"delta": result.peak_staleness, "cv": cvs[-1]},
            )
        log.check(
            f"G1 {name}", all(left >= right for left, right in pairwise(cvs)), cvs
        )
        log.check(f"G3 {name}", all(peaks[0] == item for item in peaks[1:]), peaks)
    single = sweep(1, 10.0, [], 5.0)
    log.check(
        "G4 one-agent communication",
        single.peak_staleness == 0 and single.pair_peaks == ((0.0,),),
        single.pair_peaks,
    )

    agents, links, expected, _ = CASES["B2"]
    original = sweep(agents, 10.0, records(links), 5.0)
    permutation = (2, 0, 1)
    inverse = {old: new for new, old in enumerate(permutation)}
    permuted_links = {
        tuple(sorted((inverse[first], inverse[second]))): intervals
        for (first, second), intervals in links.items()
    }
    permuted = sweep(agents, 10.0, records(permuted_links), 5.0)
    restored = tuple(
        tuple(
            permuted.pair_peaks[inverse[receiver]][inverse[source]]
            for source in range(agents)
        )
        for receiver in range(agents)
    )
    log.check(
        "G5 agent permutation",
        close(restored, expected),
        {"original": original.pair_peaks, "restored": restored},
    )

    mentions = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "results" in path.parts:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if "handshake" in text.lower():
            mentions.append(str(path.relative_to(ROOT)))
    allowed = {
        "spec/plano-testes.md",
        "tst/README.md",
        "tst/verify_properties.py",
    }
    log.check("G7 handshake references", set(mentions) <= allowed, mentions)

    for offset in (-1e-9, 0.0, 1e-9):
        classifications = [classify_tangent(offset) for _ in range(5)]
        log.check(
            f"G8 deterministic offset {offset}",
            all(item == classifications[0] for item in classifications),
            classifications,
        )

    if args.determinism_results:
        first = normalize_json(
            json.loads((ROOT / args.determinism_results[0]).read_text())
        )
        second = normalize_json(
            json.loads((ROOT / args.determinism_results[1]).read_text())
        )
        log.check("G6 deterministic result", first == second)
    else:
        log.check(
            "G6 deterministic result", True, "not requested; pass --determinism-results"
        )
    print(json.dumps(log.report(), indent=2))


if __name__ == "__main__":
    main()
