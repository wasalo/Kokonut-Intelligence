"""Organic readiness agent: synthesizes organic certification readiness, transition progress, input compliance, buffer zones, and harvest segregation data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from services.analytics.organic_certification import (
    compute_buffer_adequacy,
    compute_harvest_segregation_score,
    compute_input_compliance_pct,
    compute_organic_readiness_score,
    compute_prohibited_substance_clearance,
    compute_record_completeness,
    compute_transition_progress,
)
from services.common.logging import get_logger

logger = get_logger(__name__)

SAFETY_NOTE = (
    "Organic certification readiness outputs are advisory assessments derived from farm data. "
    "They are not guarantees of certification and should not be used as sole basis for certification decisions. "
    "Actual certification requires inspection by an accredited certification body."
)


def synthesize_organic_readiness(conn, location_id: str) -> dict[str, Any]:
    """Synthesize organic certification readiness data for a location into a public-safe summary."""
    readiness = compute_organic_readiness_score(conn, location_id)
    transition = compute_transition_progress(conn, location_id)
    input_compliance = compute_input_compliance_pct(conn, location_id)
    buffer_adequacy = compute_buffer_adequacy(conn, location_id)
    harvest_segregation = compute_harvest_segregation_score(conn, location_id)
    record_completeness = compute_record_completeness(conn, location_id)
    substance_clearance = compute_prohibited_substance_clearance(conn, location_id)

    # Determine top barriers across all dimensions
    all_barriers = list(set(
        (readiness.get("barriers") or [])
        + (transition.get("active_transitions", [{}])[0].get("barriers", []) if transition.get("active_transitions") else [])
        + (["non_compliant_inputs"] if input_compliance.get("status") == "non_compliant" else [])
        + (["buffer_zones_inadequate"] if buffer_adequacy.get("status") == "needs_improvement" else [])
        + (["harvest_segregation_incomplete"] if harvest_segregation.get("status") == "needs_improvement" else [])
        + (["records_incomplete"] if record_completeness.get("status") == "incomplete" else [])
        + (["prohibited_substance_violations"] if substance_clearance.get("status") == "violations_exist" else [])
    ))

    return {
        "location_id": location_id,
        "synthesized_at": datetime.now(timezone.utc).isoformat(),
        "overall_readiness": readiness,
        "transition_progress": transition,
        "input_compliance": input_compliance,
        "buffer_adequacy": buffer_adequacy,
        "harvest_segregation": harvest_segregation,
        "record_completeness": record_completeness,
        "prohibited_substance_clearance": substance_clearance,
        "top_barriers": all_barriers,
        "certification_readiness_status": _determine_readiness_status(readiness, input_compliance, buffer_adequacy, harvest_segregation, substance_clearance),
        "safety_note": SAFETY_NOTE,
        "limitations": [
            "Organic readiness scores are advisory assessments, not certification guarantees.",
            "Actual certification requires inspection by an accredited certification body.",
            "Transition progress depends on consistent adherence to organic practices.",
            "Input compliance reflects logged data; unreported inputs are not captured.",
            "Buffer zone adequacy is based on reported widths; field verification required.",
            "Record completeness checks table presence, not content quality.",
            "Prohibited substance clearance depends on reported usage and withdrawal periods.",
            "Agent synthesis is a draft; not verified or published without human review.",
        ],
    }


def _determine_readiness_status(
    readiness: dict,
    input_compliance: dict,
    buffer_adequacy: dict,
    harvest_segregation: dict,
    substance_clearance: dict,
) -> str:
    """Determine overall certification readiness status from sub-scores."""
    overall = readiness.get("overall_score", 0)
    input_ok = input_compliance.get("status") == "compliant"
    buffer_ok = buffer_adequacy.get("status") == "adequate"
    harvest_ok = harvest_segregation.get("status") == "compliant"
    substance_ok = substance_clearance.get("status") == "all_clear"

    if overall >= 85 and input_ok and buffer_ok and harvest_ok and substance_ok:
        return "ready_for_inspection"
    elif overall >= 60 and input_ok and substance_ok:
        return "near_ready"
    elif overall >= 40:
        return "in_progress"
    else:
        return "early_stage"
