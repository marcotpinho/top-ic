"""JSON normalization for the immutable frozen evaluator record."""


def json_value(value):
    """Convert tuple and set containers to their recorded JSON representation."""
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return [json_value(item) for item in sorted(value)]
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value
