from dataclasses import dataclass


@dataclass(frozen=True)
class RoutePreview:
    completion_times: tuple[float, ...]
    connection_times: tuple[tuple[float, ...], ...]
