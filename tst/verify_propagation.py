"""Execute analytical communication propagation cases B1-B9."""

import json

from common import CheckLog, close, records
from topcc.core.evaluation.communication import sweep

CASES = {
    "B1": (
        3,
        {(0, 1): [(2, 3)], (1, 2): [(3, 5)]},
        ((0, 7, 7), (7, 0, 5), (7, 5, 0)),
        7,
    ),
    "B2": (
        3,
        {(0, 1): [(2, 3)], (1, 2): [(4, 5)]},
        ((0, 7, 10), (7, 0, 5), (7, 5, 0)),
        10,
    ),
    "B3": (
        3,
        {(1, 2): [(2, 3)], (0, 1): [(4, 5)]},
        ((0, 5, 7), (5, 0, 7), (10, 7, 0)),
        10,
    ),
    "B4": (
        3,
        {(0, 1): [(2, 4)], (1, 2): [(3, 5)]},
        ((0, 6, 6), (6, 0, 5), (6, 5, 0)),
        6,
    ),
    "B4-control": (3, {(0, 1): [(2, 4)]}, ((0, 6, 10), (6, 0, 10), (10, 10, 0)), 10),
    "B5": (
        4,
        {(0, 1): [(1, 2)], (1, 2): [(2, 3)], (2, 3): [(3, 4)]},
        ((0, 8, 8, 10), (8, 0, 7, 7), (8, 7, 0, 6), (8, 7, 6, 0)),
        10,
    ),
    "B6": (
        3,
        {(0, 1): [(2, 3)], (1, 2): [(2, 3)], (0, 2): [(2, 3)]},
        ((0, 7, 7), (7, 0, 7), (7, 7, 0)),
        7,
    ),
    "B6b": (
        3,
        {(0, 1): [(2, 3)], (1, 2): [(2, 3)]},
        ((0, 7, 7), (7, 0, 7), (7, 7, 0)),
        7,
    ),
    "B9": (2, {(0, 1): [(5, 5)]}, ((0, 5), (5, 0)), 5),
}


def violation(peaks, recurrence):
    return sum(
        max(0.0, value - recurrence)
        for receiver, row in enumerate(peaks)
        for source, value in enumerate(row)
        if receiver != source
    )


def main():
    log = CheckLog("B-propagation")
    outputs = {}
    for name, (agents, links, expected_peaks, expected_delta) in CASES.items():
        result = sweep(agents, 10.0, records(links), 5.0)
        outputs[name] = result
        log.check(
            f"{name} peaks", close(result.pair_peaks, expected_peaks), result.pair_peaks
        )
        log.check(
            f"{name} delta",
            close(result.peak_staleness, expected_delta),
            result.peak_staleness,
        )
        log.check(
            f"{name} terminal history",
            close(result.history[-1][0], 10.0),
            result.history[-1],
        )
        log.check(
            f"{name} delta=max(peaks)",
            close(result.peak_staleness, max(map(max, result.pair_peaks))),
            result.pair_peaks,
        )
    b4 = sweep(3, 10.0, records(CASES["B4"][1]), 6.0)
    b4_control = sweep(3, 10.0, records(CASES["B4-control"][1]), 6.0)
    log.check("B7 relay CV", close(violation(b4.pair_peaks, 6), 0.0), b4.pair_peaks)
    log.check(
        "B7 control CV",
        close(violation(b4_control.pair_peaks, 6), 16.0),
        b4_control.pair_peaks,
    )
    log.check(
        "B8 asymmetry",
        outputs["B2"].pair_peaks[0][2] == 10 and outputs["B2"].pair_peaks[2][0] == 7,
        outputs["B2"].pair_peaks,
    )
    print(json.dumps(log.report(), indent=2))


if __name__ == "__main__":
    main()
