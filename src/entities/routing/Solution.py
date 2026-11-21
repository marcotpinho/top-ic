from dataclasses import dataclass, field

from .Visit import Visit


@dataclass(frozen=True)
class Solution:
    routes: tuple[tuple[Visit, ...], ...]
    evaluation: object = field(default=None, compare=False, repr=False)
    _key: tuple = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "routes", tuple(tuple(r) for r in self.routes))
        object.__setattr__(
            self,
            "_key",
            tuple(
                tuple((v.kind, v.position, v.velocity, v.task_id) for v in route)
                for route in self.routes
            ),
        )

    @property
    def key(self) -> tuple:
        return self._key

    @property
    def objectives(self) -> tuple[float, ...] | None:
        return self.evaluation.objectives if self.evaluation else None

    def dominates(self, other: "Solution") -> bool:
        if self.objectives is None or other.objectives is None:
            return False
        return all(a <= b for a, b in zip(self.objectives, other.objectives)) and any(
            a < b for a, b in zip(self.objectives, other.objectives)
        )
