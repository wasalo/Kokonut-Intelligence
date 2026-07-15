"""Integration tests for stakeholder decision lineage and approval boundaries."""

import pytest

from services.analytics import stakeholder_decisions as decisions
from services.ingestion.base import get_db


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_decision_requires_human_approval_before_execution():
    conn = _db()
    decision_id = None
    try:
        created = decisions.create_decision(
            conn,
            "Protect minimum water access",
            "Choose a drought response without reducing household access.",
            "policy",
            decision_key="TEST-SD-WATER-001",
            created_by_party_id="a0000000-0000-0000-0000-000000001000",
        )
        decision_id = created["id"]
        assert decisions.link_execution(conn, decision_id, decision_log_id=decision_id) is None
        assert decisions.submit_decision(conn, decision_id)["status"] == "submitted"

        decisions.add_participant(
            conn, decision_id, party_id="a0000000-0000-0000-0000-000000001001",
            stakeholder_role="affected", participation_status="participated", consent_checked=True,
        )
        decisions.add_tradeoff(
            conn, decision_id, "Household access could be harmed", "harm", severity=8,
            mitigation="Protect minimum access first",
        )
        decisions.add_evidence(
            conn, decision_id, "metric", "Verified soil moisture trend", evidence_role="supporting",
            evidence_maturity=4, verified=True,
        )
        decisions.record_outcome(conn, decision_id, "harm", "No material access disruption observed", outcome_status="verified")

        approved = decisions.approve_decision(
            conn, decision_id, "a0000000-0000-0000-0000-000000001002"
        )
        assert approved["approval_status"] == "approved"

        lineage = decisions.get_decision(conn, decision_id)
        assert lineage["participant_count"] == 1
        assert lineage["unresolved_harm_count"] == 1
        assert lineage["verified_evidence_count"] == 1
        assert lineage["outcome_count"] == 1
    finally:
        if decision_id:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM stakeholder_decision WHERE id = %s::uuid", (decision_id,))
            conn.commit()
        conn.close()


def test_approval_requires_explicit_approver():
    conn = _db()
    decision_id = None
    try:
        decision_id = decisions.create_decision(
            conn, "Test approval", "Approval must identify a human party.", "governance",
            decision_key="TEST-SD-APPROVAL-001",
        )["id"]
        decisions.submit_decision(conn, decision_id)
        with pytest.raises(ValueError, match="human approving party"):
            decisions.approve_decision(conn, decision_id, "")
    finally:
        if decision_id:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM stakeholder_decision WHERE id = %s::uuid", (decision_id,))
            conn.commit()
        conn.close()
