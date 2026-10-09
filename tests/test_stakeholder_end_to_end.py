"""Cross-domain stakeholder journey for the definition of done."""

import pytest

from services.analytics import consent_resolver, stakeholder_identity_resolution, stakeholder_trust
from services.analytics import stakeholder_decisions as decisions
from services.export.report_generator import generate_stakeholder_cockpit
from services.ingestion.base import get_db


LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
SUBJECT_ID = "b0000000-0000-0000-0000-000000009201"
REVIEWER_ID = "b0000000-0000-0000-0000-000000009202"
DECISION_KEY = "DOD-E2E-STAKEHOLDER-001"


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_identity_consent_decision_trust_and_cockpit_journey():
    conn = _db()
    decision_id = None
    feedback_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM stakeholder_decision WHERE decision_key = %s", (DECISION_KEY,))
            cur.execute(
                """INSERT INTO party (id, party_type, display_name, privacy_level)
                   VALUES (%s::uuid, 'person', 'E2E Resident', 'public'),
                          (%s::uuid, 'person', 'E2E Reviewer', 'public')
                   ON CONFLICT (id) DO UPDATE
                   SET party_type = EXCLUDED.party_type,
                       display_name = EXCLUDED.display_name,
                       privacy_level = EXCLUDED.privacy_level""",
                (SUBJECT_ID, REVIEWER_ID),
            )
        conn.commit()

        case = stakeholder_identity_resolution.propose_link(
            conn, "dod-e2e", "farmer_profile_id", "E2E-001", SUBJECT_ID, "person",
            confidence=0.95, evidence=[{"source": "e2e"}],
        )
        stakeholder_identity_resolution.review_link(
            conn, str(case["id"]), REVIEWER_ID, approved=True, notes="E2E identity review complete",
        )
        consent_resolver.record_consent(
            conn, SUBJECT_ID, "stakeholder_feedback", "public_summary",
            scope_type="location", scope_id=LOCATION_ID,
        )
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO stakeholder_feedback
                   (location_id, feedback_type, stakeholder_group, feedback_date, feedback_text,
                    consent_given, consent_scope, status, party_id)
                   VALUES (%s::uuid, 'community_need', 'community', CURRENT_DATE, 'E2E feedback',
                           TRUE, 'public_summary', 'draft', %s::uuid) RETURNING id""",
                (LOCATION_ID, SUBJECT_ID),
            )
            feedback_id = cur.fetchone()[0]
            cur.execute(
                """UPDATE stakeholder_feedback
                   SET is_public = TRUE, status = 'published', public_summary = 'E2E public summary'
                   WHERE id = %s::uuid""", (feedback_id,)
            )
        conn.commit()

        created = decisions.create_decision(
            conn, "E2E water access decision", "Protect minimum access while responding to drought.",
            "policy", decision_key=DECISION_KEY, scope_type="location", scope_id=LOCATION_ID,
            created_by_party_id=SUBJECT_ID,
        )
        decision_id = created["id"]
        decisions.submit_decision(conn, decision_id)
        decisions.add_participant(
            conn, decision_id, party_id=SUBJECT_ID, stakeholder_role="affected",
            participation_status="participated", consent_checked=True,
        )
        tradeoff = decisions.add_tradeoff(
            conn, decision_id, "Expansion may reduce household water access", "harm",
            party_id=SUBJECT_ID, severity=8, mitigation="Protect minimum access",
        )
        decisions.resolve_tradeoff(conn, tradeoff["id"], accepted=True)
        decisions.add_evidence(
            conn, decision_id, "stakeholder_feedback", "E2E public feedback evidence",
            evidence_role="input", source_id=feedback_id, evidence_maturity=4, verified=True,
        )
        approved = decisions.approve_decision(
            conn, decision_id, REVIEWER_ID, approval_evidence=[{"review": "e2e"}],
        )
        assert approved["approval_status"] == "approved"
        stakeholder_trust.record_evidence(
            conn, SUBJECT_ID, "participation", "supporting", "stakeholder_decision",
            "Affected party participated in the governed decision", source_id=decision_id,
            confidence=0.9, uncertainty=0.1, audience="public",
        )
        lineage = decisions.get_decision(conn, decision_id)
        cockpit = generate_stakeholder_cockpit(conn)
        assert lineage["participant_count"] == 1
        assert lineage["verified_evidence_count"] == 1
        assert cockpit["report_type"] == "stakeholder_cockpit"
        assert "public_safe" in cockpit
    finally:
        with conn.cursor() as cur:
            if decision_id:
                cur.execute("DELETE FROM stakeholder_decision WHERE id = %s::uuid", (decision_id,))
            if feedback_id:
                cur.execute("DELETE FROM stakeholder_feedback WHERE id = %s::uuid", (feedback_id,))
            cur.execute("DELETE FROM party_trust_evidence WHERE subject_party_id = %s::uuid", (SUBJECT_ID,))
            cur.execute("DELETE FROM party_resolution_case WHERE source_system = 'dod-e2e'")
            cur.execute("DELETE FROM party_identifier WHERE source_system = 'dod-e2e'")
        conn.commit()
        conn.close()


from unittest.mock import MagicMock


def test_decision_rejects_unresolved_harm_before_approval():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"unresolved_harm_count": 2}
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="unresolved material harm"):
        decisions.approve_decision(mock_conn, "d1", "approver-id")


def test_decision_submit_requires_draft_status():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    result = decisions.submit_decision(mock_conn, "nonexistent-id")
    assert result is None
