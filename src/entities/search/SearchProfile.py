from dataclasses import dataclass, field

from .NeighborhoodTiming import NeighborhoodTiming


@dataclass
class SearchProfile:
    search_loop_seconds: float = 0.0
    evaluation_seconds: float = 0.0
    evaluator_seconds: float = 0.0
    parallel_dispatch_seconds: float = 0.0
    parallel_wait_seconds: float = 0.0
    worker_evaluator_seconds: float = 0.0
    oracle_seconds: float = 0.0
    candidate_preparation_seconds: float = 0.0
    duplicate_check_seconds: float = 0.0
    candidate_counters_seconds: float = 0.0
    archive_update_seconds: float = 0.0
    front_update_seconds: float = 0.0
    pool_update_seconds: float = 0.0
    pool_merge_seconds: float = 0.0
    pool_dominance_seconds: float = 0.0
    pool_crowding_seconds: float = 0.0
    pool_bookkeeping_seconds: float = 0.0
    recording_seconds: float = 0.0
    base_selection_seconds: float = 0.0
    pool_maintenance_seconds: float = 0.0
    budget_repair_seconds: float = 0.0
    budget_precheck_seconds: float = 0.0
    budget_contact_check_seconds: float = 0.0
    neighborhoods: dict[str, NeighborhoodTiming] = field(default_factory=dict)

    @classmethod
    def for_neighborhoods(cls, names: tuple[str, ...]) -> "SearchProfile":
        return cls(neighborhoods={name: NeighborhoodTiming() for name in names})
