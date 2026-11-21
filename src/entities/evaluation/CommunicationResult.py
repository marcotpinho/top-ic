from dataclasses import dataclass

from .ContactRecord import ContactRecord


@dataclass(frozen=True)
class CommunicationResult:
    peak_staleness: float
    contacts: tuple[ContactRecord, ...]
    history: tuple[tuple[float, float, float], ...]
    final_clock: tuple[tuple[float, ...], ...]
    bottleneck: tuple[int, int, float, str] | None
    numerical_status: str = "resolved"
    pair_peaks: tuple[tuple[float, ...], ...] = ()
    integrated_excess: float = 0.0
