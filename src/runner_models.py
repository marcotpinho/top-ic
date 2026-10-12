"""Serializable optimization run result."""

from dataclasses import dataclass


@dataclass
class RunResult:
    problem: object
    config: object
    front: list
    statistics: dict
    elapsed_seconds: float
    status: str
    candidate_bank: tuple = ()
    dominated_archive: tuple = ()
