"""Compatibility façade for the neighborhood package."""

from .neighborhoods.common import edited, fresh_id, normalize
from .neighborhoods.core import neighbors, communication_neighbors
from .neighborhoods.registry import (
    COMM_NEIGHBORHOODS,
    ICC_NEIGHBORHOODS,
    SINGLE_NEIGHBORHOODS,
    TEAM_NEIGHBORHOODS,
)
