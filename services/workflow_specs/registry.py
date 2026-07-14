"""In-process workflow specification registry."""

from typing import Dict, Tuple

from .model import WorkflowSpec

_SPECS: Dict[str, WorkflowSpec] = {}


def register(spec: WorkflowSpec) -> WorkflowSpec:
    if spec.id in _SPECS:
        raise ValueError(f"workflow spec already registered: {spec.id}")
    _SPECS[spec.id] = spec
    return spec


def get_spec(spec_id: str) -> WorkflowSpec:
    try:
        return _SPECS[spec_id]
    except KeyError as exc:
        raise KeyError(f"unknown workflow spec: {spec_id}") from exc


def list_specs() -> Tuple[WorkflowSpec, ...]:
    return tuple(_SPECS[key] for key in sorted(_SPECS))


def load_builtin_specs() -> None:
    """Import built-in specifications once."""
    from . import carbon_retirement, event_bus, work_item  # noqa: F401
