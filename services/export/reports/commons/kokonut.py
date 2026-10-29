"""Report generators: kokonut."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from ..common import _looks_like_uuid, _serialize_rows
from ..scope import require_network_scope

# Keep these projections aligned with the public views in
# schemas/postgres/041_kokonut_commons_governance.sql. The views currently
# expose their source-table columns followed by the evidence label.
_PUBLIC_VIEW_COLUMNS = {
    "v_public_anti_capture_governance_policy": (
        "id",
        "location_id",
        "policy_name",
        "governance_body",
        "policy_scope",
        "voting_method",
        "voting_cap_pct",
        "quadratic_or_conviction_enabled",
        "one_person_one_vote_enabled",
        "sybil_resistance_method",
        "worker_or_operator_veto_enabled",
        "community_veto_enabled",
        "delegation_limits",
        "enforcement_mode",
        "policy_summary",
        "public_summary",
        "evidence_maturity",
        "status",
        "metadata",
        "source_system",
        "source_id",
        "source_raw",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "evidence_maturity_label",
    ),
    "v_public_commons_redistribution_policy": (
        "id",
        "location_id",
        "policy_name",
        "scenario_name",
        "policy_scope",
        "policy_status",
        "revenue_basis",
        "commons_allocation_pct",
        "local_cooperative_allocation_pct",
        "operator_allocation_pct",
        "digital_commons_allocation_pct",
        "reserve_allocation_pct",
        "trigger_conditions",
        "enforcement_mode",
        "audit_cadence",
        "policy_summary",
        "public_summary",
        "evidence_maturity",
        "status",
        "metadata",
        "source_system",
        "source_id",
        "source_raw",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "evidence_maturity_label",
    ),
    "v_public_federation_protocol": (
        "id",
        "protocol_name",
        "target_region",
        "federation_scope",
        "permissionless_forking_enabled",
        "local_adaptation_rights",
        "mutual_aid_commitments",
        "shared_infrastructure",
        "onboarding_requirements",
        "anti_extractive_safeguards",
        "conflict_resolution_path",
        "protocol_status",
        "public_summary",
        "evidence_maturity",
        "status",
        "metadata",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "evidence_maturity_label",
    ),
    "v_public_algorithmic_redistribution_mechanism": (
        "id",
        "location_id",
        "mechanism_name",
        "mechanism_type",
        "beneficiary_scope",
        "allocation_formula",
        "funding_source",
        "eligibility_criteria",
        "privacy_safeguards",
        "implementation_status",
        "enforcement_mode",
        "mechanism_summary",
        "public_summary",
        "evidence_maturity",
        "status",
        "metadata",
        "source_system",
        "source_id",
        "source_raw",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "evidence_maturity_label",
    ),
    "v_public_participatory_signal_experiment": (
        "id",
        "experiment_name",
        "signal_type",
        "governance_scope",
        "decision_binding",
        "experiment_status",
        "participation_rules",
        "moderation_policy",
        "safety_boundaries",
        "public_summary",
        "evidence_maturity",
        "status",
        "metadata",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "evidence_maturity_label",
    ),
}


def _fetch_public_view(
    conn,
    view_name: str,
    location_id: str | None,
    order_by: str = "id",
    *,
    network_scope: bool = False,
) -> list[dict]:
    if not network_scope and not location_id:
        raise ValueError(f"{view_name} requires an explicit location_id")

    if network_scope and location_id:
        raise ValueError(f"{view_name} cannot combine network and location scope")

    if not network_scope and not _looks_like_uuid(location_id):
        raise ValueError(f"{view_name} requires a valid location_id")

    # Validate identifiers to prevent SQL injection
    import re

    _IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    _ORDER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(?:\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*)*$")
    if not _IDENT_RE.match(view_name):
        raise ValueError(f"Invalid view name: {view_name}")
    if not _ORDER_RE.match(order_by):
        raise ValueError(f"Invalid order_by: {order_by}")
    columns = _PUBLIC_VIEW_COLUMNS.get(view_name)
    if columns is None:
        raise ValueError(f"Unsupported public view: {view_name}")
    projection = ", ".join(columns)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if network_scope:
            cur.execute(f"SELECT {projection} FROM {view_name} ORDER BY {order_by}")
        else:
            cur.execute(
                f"SELECT {projection} FROM {view_name} WHERE location_id = %s OR location_id IS NULL ORDER BY {order_by}",
                (location_id,),
            )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
    return rows


def generate_anti_capture_governance(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    policies = _fetch_public_view(
        conn, "v_public_anti_capture_governance_policy", location_id, "policy_scope, policy_name"
    )
    return {
        "report_type": "anti_capture_governance",
        "location_id": location_id,
        "policies": _serialize_rows(policies),
        "community_veto_count": sum(1 for row in policies if row.get("community_veto_enabled")),
        "operator_veto_count": sum(1 for row in policies if row.get("worker_or_operator_veto_enabled")),
        "limitations": [
            "Anti-capture policies are public governance evidence and may be offchain unless enforcement mode says otherwise.",
            "Do not claim one-person-one-vote, quadratic voting, or smart-contract enforcement unless explicitly documented.",
            "Representation requirements must remain lawful, consented, and privacy-safe.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_redistribution_policy(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    policies = _fetch_public_view(
        conn, "v_public_commons_redistribution_policy", location_id, "policy_status, policy_scope, policy_name"
    )
    return {
        "report_type": "redistribution_policy",
        "location_id": location_id,
        "policies": _serialize_rows(policies),
        "active_policy_count": sum(1 for row in policies if row.get("policy_status") == "active"),
        "scenario_policy_count": sum(1 for row in policies if row.get("policy_scope") == "scenario"),
        "limitations": [
            "Redistribution policies are scenario-specific and should not be generalized across farms without matching records.",
            "Current policy percentages and proposed scenarios are separate; proposed policies are not commitments.",
            "Private recipient identities and private capital terms are excluded.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_federation_mutual_aid(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    require_network_scope("federation_mutual_aid", location_id)
    protocols = _fetch_public_view(
        conn,
        "v_public_federation_protocol",
        None,
        "protocol_status, federation_scope, protocol_name",
        network_scope=True,
    )
    return {
        "report_type": "federation_mutual_aid",
        "location_id": location_id,
        "protocols": _serialize_rows(protocols),
        "permissionless_forking_count": sum(1 for row in protocols if row.get("permissionless_forking_enabled")),
        "limitations": [
            "Federation protocols support reuse and local adaptation; they are not unlimited-scaling guarantees.",
            "New communities require local registry, governance, cultural, financial, and evidence records.",
            "Anti-extractive safeguards should be reviewed before public replication claims expand.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_algorithmic_redistribution(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    mechanisms = _fetch_public_view(
        conn,
        "v_public_algorithmic_redistribution_mechanism",
        location_id,
        "implementation_status, mechanism_type, mechanism_name",
    )
    return {
        "report_type": "algorithmic_redistribution",
        "location_id": location_id,
        "mechanisms": _serialize_rows(mechanisms),
        "active_or_pilot_count": sum(
            1 for row in mechanisms if row.get("implementation_status") in {"active", "pilot"}
        ),
        "limitations": [
            "Redistribution mechanisms are not onchain payment implementations unless enforcement mode documents smart-contract execution.",
            "Public reports exclude private eligibility, protected-class details, and household-level beneficiary data.",
            "Airdrops, progressive fees, or reparations claims require separate governed implementation records.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_participatory_signal(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    require_network_scope("participatory_signal", location_id)
    experiments = _fetch_public_view(
        conn,
        "v_public_participatory_signal_experiment",
        None,
        "experiment_status, signal_type, experiment_name",
        network_scope=True,
    )
    return {
        "report_type": "participatory_signal",
        "location_id": location_id,
        "experiments": _serialize_rows(experiments),
        "advisory_count": sum(1 for row in experiments if row.get("decision_binding") == "advisory"),
        "limitations": [
            "Participatory signal experiments are advisory unless decision binding states otherwise and human review approves use.",
            "Meme, vibes, and story signals cannot override evidence maturity, privacy, or treasury controls.",
            "Moderation and safety boundaries must be enforced before publication.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Ecological Modeling Reports
# ---------------------------------------------------------------------------


