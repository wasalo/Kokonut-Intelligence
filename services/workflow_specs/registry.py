"""In-process workflow specification registry."""

from dataclasses import replace
from typing import Dict, Tuple

from .metadata import metadata_for
from .model import WorkflowSpec

_SPECS: Dict[str, WorkflowSpec] = {}


def register(spec: WorkflowSpec) -> WorkflowSpec:
    if spec.id in _SPECS:
        raise ValueError(f"workflow spec already registered: {spec.id}")
    if not spec.metadata.governance_controls and not spec.metadata.data_sources:
        spec = replace(spec, metadata=metadata_for(spec.id))
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
    from . import (  # noqa: F401
        ai_summary,
        budget,
        carbon_retirement,
        cooperative_order,
        coordination_alliance,
        data_stream_post,
        emergency_incident,
        event_bus,
        extension_enrollment,
        farm_activity,
        governance,
        harvest_event,
        impact_claim,
        insurance_claim,
        market_order,
        metric_value,
        objective,
        pest_intervention,
        project,
        report_snapshot,
        stakeholder_feedback,
        traceability_batch,
        work_item,
    )
