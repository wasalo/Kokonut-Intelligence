"""Report generators: kokonut."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from ..common import _serialize_rows


def _fetch_public_view(conn, view_name: str, location_id: str = None, order_by: str = "id") -> list[dict]:
    # Validate identifiers to prevent SQL injection
    import re

    _IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    _ORDER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(?:\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*)*$")
    if not _IDENT_RE.match(view_name):
        raise ValueError(f"Invalid view name: {view_name}")
    if not _ORDER_RE.match(order_by):
        raise ValueError(f"Invalid order_by: {order_by}")

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            f"SELECT * FROM {view_name} WHERE location_id = %s OR location_id IS NULL ORDER BY {order_by}",
            (location_id,),
        )
    else:
        cur.execute(f"SELECT * FROM {view_name} ORDER BY {order_by}")
    rows = [dict(r) for r in cur.fetchall()]
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
    protocols = _fetch_public_view(
        conn, "v_public_federation_protocol", None, "protocol_status, federation_scope, protocol_name"
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
    experiments = _fetch_public_view(
        conn, "v_public_participatory_signal_experiment", None, "experiment_status, signal_type, experiment_name"
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


