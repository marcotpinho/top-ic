from dataclasses import dataclass


@dataclass(frozen=True)
class ContactRecord:
    agents: tuple[int, int]
    raw: tuple[tuple[float, float], ...]
    effective: tuple[tuple[float, float], ...]
