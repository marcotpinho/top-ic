"""Execute analytical contact cases A1-A9 from spec/plano-testes.md."""

import json
from collections import Counter
from math import sqrt

from common import CheckLog, close, piece, trajectory
from topcc.core.evaluation.communication import evaluate_communication, sweep
from topcc.core.evaluation.contacts import pair_contacts
from topcc.entities.evaluation.ContactRecord import ContactRecord
from topcc.entities.evaluation.ContactUncertain import ContactUncertain


def moving(position, velocity, duration=10.0, acceleration=(0.0, 0.0), completion=None):
    return trajectory(
        [piece(position, velocity, acceleration, duration)],
        duration if completion is None else completion,
    )


def evaluate_pair(first, second, radius=2.0, recurrence=5.0):
    horizon = max(first.completion_time, second.completion_time)
    intervals = pair_contacts(first, second, horizon, radius)
    communication = sweep(
        2,
        horizon,
        [ContactRecord((0, 1), intervals, intervals)],
        recurrence,
    )
    return intervals, communication


def main():
    log = CheckLog("A-contacts")
    first = moving((0, 0), (1, 0))
    intervals, result = evaluate_pair(first, moving((0, 1), (1, 0)))
    log.check("A1 intervals", close(intervals, ((0.0, 10.0),), 1e-7), intervals)
    log.check("A1 peaks", close(result.pair_peaks, ((0, 0), (0, 0))), result.pair_peaks)

    intervals, result = evaluate_pair(first, moving((0, 3), (1, 0)))
    violation = sum(max(0.0, value - 5.0) for row in result.pair_peaks for value in row)
    log.check("A2 intervals", intervals == (), intervals)
    log.check(
        "A2 peaks", close(result.pair_peaks, ((0, 10), (10, 0))), result.pair_peaks
    )
    log.check("A2 CV", close(violation, 10.0), violation)

    intervals, result = evaluate_pair(first, moving((10, 1), (-1, 0)))
    expected = ((5 - sqrt(3) / 2, 5 + sqrt(3) / 2),)
    log.check("A3 intervals", close(intervals, expected, 1e-7), intervals)
    log.check(
        "A3 peaks",
        close(result.pair_peaks, ((0, expected[0][0]), (expected[0][0], 0)), 1e-7),
        result.pair_peaks,
    )

    tangent = moving((5, 2), (0, 0))
    intervals, result = evaluate_pair(first, tangent)
    log.check("A4 point contact", close(intervals, ((5.0, 5.0),), 1e-9), intervals)
    log.check("A4 peaks", close(result.pair_peaks, ((0, 5), (5, 0))), result.pair_peaks)

    for name, offset in (("A5a", 1e-10), ("A5b", -1e-10)):
        try:
            pair_contacts(first, moving((5, 2 + offset), (0, 0)), 10.0, 2.0)
        except ContactUncertain:
            unresolved = True
        else:
            unresolved = False
        log.check(f"{name} unresolved", unresolved)
    intervals = pair_contacts(first, moving((5, 2 + 1e-6), (0, 0)), 10.0, 2.0)
    log.check("A5c empty", intervals == (), intervals)
    intervals = pair_contacts(first, moving((5, 2 - 1e-6), (0, 0)), 10.0, 2.0)
    half_width = sqrt(4e-6 - 1e-12)
    log.check(
        "A5d narrow interval",
        close(intervals, ((5 - half_width, 5 + half_width),), 1e-9),
        intervals,
    )

    accelerated = moving((22.5, 0), (-10, 0), acceleration=(2, 0))
    intervals, result = evaluate_pair(accelerated, moving((0, 0), (0, 0)))
    expected = ((5 - sqrt(4.5), 5 - sqrt(0.5)), (5 + sqrt(0.5), 5 + sqrt(4.5)))
    log.check("A6 quartic intervals", close(intervals, expected, 1e-7), intervals)
    log.check(
        "A6 peaks",
        close(result.peak_staleness, 5 - sqrt(4.5), 1e-7),
        result.peak_staleness,
    )

    two_piece = trajectory(
        [piece((0, 0), (1, 0), (0, 0), 5, 0), piece((5, 0), (1, 0), (0, 0), 5, 5)],
        10,
    )
    intervals, result = evaluate_pair(two_piece, moving((5, 1), (0, 0)))
    expected = ((5 - sqrt(3), 5 + sqrt(3)),)
    log.check("A7 merged pieces", close(intervals, expected, 1e-7), intervals)
    log.check(
        "A7 peaks",
        close(result.peak_staleness, 5 - sqrt(3), 1e-7),
        result.peak_staleness,
    )

    short = moving((0, 0), (1, 0), duration=4, completion=4)
    long = moving((4, -5), (0, 1))
    intervals, result = evaluate_pair(short, long)
    expected = (((9 - sqrt(7)) / 2, 7.0),)
    log.check("A8 terminal presence", close(intervals, expected, 1e-7), intervals)
    log.check(
        "A8 peaks",
        close(result.peak_staleness, expected[0][0], 1e-7),
        result.peak_staleness,
    )

    far10 = moving((100, 100), (0, 0), 10, completion=10)
    first_result = evaluate_communication((short, long, far10), 2.0, 5.0)
    metrics = Counter()
    control = moving((101, 100), (0, 0), 10, completion=10)
    evaluate_communication(
        (short, long, control),
        2.0,
        5.0,
        parent_communication=first_result,
        parent_horizon=10,
        reusable_agents={0, 1},
        metrics=metrics,
    )
    log.check(
        "A9 same-horizon reuse",
        metrics == {"pairs_reused": 1, "pairs_rebuilt": 2},
        dict(metrics),
    )
    metrics = Counter()
    far12 = moving((100, 100), (0, 0), 12, completion=12)
    changed = evaluate_communication(
        (short, long, far12),
        2.0,
        5.0,
        parent_communication=first_result,
        parent_horizon=10,
        reusable_agents={0, 1},
        metrics=metrics,
    )
    log.check(
        "A9 changed-horizon rebuild", metrics == {"pairs_rebuilt": 3}, dict(metrics)
    )
    log.check(
        "A9 changed peak",
        close(changed.pair_peaks[0][1], 5.0, 1e-7),
        changed.pair_peaks,
    )
    print(json.dumps(log.report(), indent=2))


if __name__ == "__main__":
    main()
