"""Kokonut Intelligence Prefect workflow definitions.

Each flow wraps an existing CLI tool as a Prefect flow.
Flows are scheduled via Prefect UI or deployment YAML.
"""

def __getattr__(name):
    """Retain legacy decorator exports without loading Prefect on package import."""
    if name not in {"flow", "task"}:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from services.core.adapters import prefect

    return getattr(prefect, name)
