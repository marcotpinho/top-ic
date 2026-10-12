"""The single source of truth for available neighborhood families."""

SINGLE_NEIGHBORHOODS = (
    "insert",
    "remove",
    "replace",
    "reorder",
    "velocity",
    "velocity_dp",
)
TEAM_NEIGHBORHOODS = SINGLE_NEIGHBORHOODS + ("assignment",)
COMM_NEIGHBORHOODS = (
    "excursion",
    "wait",
    "meeting",
    "duplicate_rendezvous",
    "free_move",
    "free_remove",
    "unlink",
)
ICC_NEIGHBORHOODS = (
    "remove",
    "replace",
    "assignment",
    "reorder",
    "insert",
    "excursion",
    "meeting",
    "unlink",
)
