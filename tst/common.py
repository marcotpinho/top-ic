"""Shared analytical verification helpers for the TOP-ICC test plan."""

from math import isclose

from topcc.evaluation_core.communication import ContactRecord
from topcc.evaluation_core.trajectory import AgentTrajectory, MotionPiece, State


def piece(position, velocity, acceleration, duration, start_time=0.0):
    return MotionPiece(
        tuple(position),
        tuple(velocity),
        tuple(acceleration),
        float(duration),
        float(start_time),
    )


def trajectory(pieces, completion):
    last = pieces[-1].state(pieces[-1].duration)
    return AgentTrajectory(
        tuple(pieces),
        float(completion),
        State(pieces[0].position, pieces[0].velocity),
        State(last.position, (0.0, 0.0)),
    )


def records(spec):
    return [
        ContactRecord(pair, tuple(intervals), tuple(intervals))
        for pair, intervals in spec.items()
    ]


def close(actual, expected, tolerance=1e-9):
    if isinstance(expected, (tuple, list)):
        return len(actual) == len(expected) and all(
            close(left, right, tolerance) for left, right in zip(actual, expected)
        )
    return isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tolerance)


class CheckLog:
    def __init__(self, suite):
        self.suite = suite
        self.checks = []

    def check(self, name, condition, evidence=None):
        passed = bool(condition)
        self.checks.append({"name": name, "passed": passed, "evidence": evidence})
        if not passed:
            raise AssertionError(f"{name}: {evidence}")

    def report(self):
        return {
            "schema_version": 1,
            "suite": self.suite,
            "status": "ok",
            "checks": self.checks,
            "passed": sum(item["passed"] for item in self.checks),
            "failed": sum(not item["passed"] for item in self.checks),
        }
