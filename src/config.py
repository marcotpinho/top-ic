from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Configuration for a TOP-CC optimization run.

    Constructed by the CLI and passed explicitly to all components.
    Do NOT use as a global singleton — create one per optimization run.
    """

    max_iterations: int = 1000
    max_time: int = 60
    seed: int = 42
    archive_size: int = 40
    front_selection_prob: float = 0.9
    algorithm: str = "unique_vis"
    out_dir: str = "out/"
    img_dir: str = "imgs/"
    save_results: bool = False
    plot_results: bool = False
    predict_distances: bool = False
    map_file: Optional[str] = None
    db_path: Optional[str] = None
    save_to_db: bool = False


@dataclass(frozen=True)
class ProblemContext:
    """Immutable problem parameters shared across all solutions in a run.

    Replaces the old Solution.set_parameters() class-level mutable state.
    """

    begin: int
    end: int
    num_agents: int
    budget: list[float] = field(default_factory=list)
    speeds: list[float] = field(default_factory=list)
