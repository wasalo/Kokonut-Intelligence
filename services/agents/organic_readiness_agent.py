"""Organic readiness agent: synthesizes organic certification readiness, transition progress, input compliance, buffer zones, and harvest segregation data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.agents.base import (
    SynthesisAgent,
    require_synthesis_location_id,
)
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
    location_id = require_synthesis_location_id(location_id)
    # The analytics module intentionally retains its stable, unqualified SQL
    # contract. In the signed worker this search path contains only the
    # location-filtered projection schema, never public base tables.
    with conn.cursor() as cursor:
        cursor.execute("SET LOCAL search_path = kokonut_agent_source, pg_catalog")

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


class OrganicReadinessSynthesisAgent(SynthesisAgent):
    """Run the legacy readiness calculations through signed source views."""

    task_key = "organic_readiness_synthesis"
    summary_type = "organic_readiness"
    read_collection = "organic_readiness_assessment"
    model_version = "organic-readiness-agent-v1"
    source_tables = [
        "organic_readiness_assessment",
        "organic_transition_plan",
        "organic_input_audit",
        "buffer_zone",
        "harvest_handling_record",
        "organic_certification_record",
        "organic_compliance_checklist",
        "prohibited_substance_record",
    ]
    source_reference_views = {
        "organic_readiness_assessment": "v_public_organic_readiness",
        "organic_transition_plan": "v_public_organic_transition",
        "organic_input_audit": "v_public_organic_input_audit",
        "buffer_zone": "v_public_buffer_zone_status",
        "harvest_handling_record": "v_public_harvest_segregation",
        "organic_certification_record": "v_public_organic_certifications",
        "prohibited_substance_record": "v_public_prohibited_substance_audit",
    }
    # Compliance checklist rows have no governed review lifecycle and contain
    # inspector identities, findings, and evidence. Keep the scoped ID-only
    # view for the legacy completeness count, but do not publish row IDs as
    # reviewer provenance until those records have an approved lifecycle.

    def synthesize(self, conn, location_id=None):
        return synthesize_organic_readiness(conn, location_id)


agent = OrganicReadinessSynthesisAgent()


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
