"""DoD-closure integration tests for identity and consent enforcement."""

import pytest

from services.analytics import consent_resolver, stakeholder_identity_resolution, stakeholder_trust, cooperative_governance
from services.analytics import cooperative as cooperative_service
from services.ingestion.base import get_db


PILOT_LOCATION = "a0000000-0000-0000-0000-000000000001"
PARTY_ID = "b0000000-0000-0000-0000-000000009101"
REVIEWER_ID = "b0000000-0000-0000-0000-000000009102"
BUYER_ID = "b0000000-0000-0000-0000-000000009103"


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def _parties(conn):
    # Consent history is immutable, so deterministic fixture parties are reused.
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO party (id, party_type, display_name)
               VALUES (%s::uuid, 'person', 'Resolution Subject'),
                      (%s::uuid, 'person', 'Resolution Reviewer')
               ON CONFLICT (id) DO UPDATE
               SET party_type = EXCLUDED.party_type,
                   display_name = EXCLUDED.display_name""",
            (PARTY_ID, REVIEWER_ID),
        )
    conn.commit()


def test_identity_resolution_requires_human_review():
    conn = _db()
    case_id = None
    try:
        _parties(conn)
        case = stakeholder_identity_resolution.propose_link(
            conn, "dod-test", "farmer_profile_id", "F-DOD-001", PARTY_ID, "person",
            match_method="manual", confidence=0.8, evidence=[{"source": "test"}],
        )
        case_id = case["id"]
        assert stakeholder_identity_resolution.verified_party_for_source(
            conn, "dod-test", "farmer_profile_id", "F-DOD-001"
        ) is None
        reviewed = stakeholder_identity_resolution.review_link(
            conn, case_id, REVIEWER_ID, approved=True, notes="Reviewed source record and identity evidence.",
        )
        assert reviewed["status"] == "approved"
        linked = stakeholder_identity_resolution.verified_party_for_source(
            conn, "dod-test", "farmer_profile_id", "F-DOD-001"
        )
        assert str(linked["party_id"]) == PARTY_ID
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM party_resolution_case WHERE source_system = 'dod-test'")
            cur.execute("DELETE FROM party_identifier WHERE source_system = 'dod-test'")
        conn.commit()
        conn.close()


def test_public_feedback_requires_canonical_consent():
    conn = _db()
    feedback_id = None
    try:
        _parties(conn)
        consent_resolver.record_consent(
            conn, PARTY_ID, "stakeholder_feedback", "public_summary",
            scope_type="location", scope_id=PILOT_LOCATION,
        )
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO stakeholder_feedback
                   (location_id, feedback_type, stakeholder_group, feedback_date, feedback_text,
                    consent_given, consent_scope, is_public, status, party_id)
                   VALUES (%s::uuid, 'community_need', 'community', CURRENT_DATE,
                           'Test public feedback', TRUE, 'public_summary', FALSE, 'draft', %s::uuid)
                   RETURNING id""",
                (PILOT_LOCATION, PARTY_ID),
            )
            feedback_id = cur.fetchone()[0]
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE stakeholder_feedback
                   SET is_public = TRUE, status = 'published', public_summary = 'Published test summary'
                   WHERE id = %s::uuid""", (feedback_id,)
            )
        conn.commit()
        consent_event = consent_resolver.list_effective_consent(conn, PARTY_ID)[0]
        consent_resolver.withdraw_consent(conn, consent_event["consent_event_id"], "Test withdrawal")
        with pytest.raises(Exception, match="canonical consent"):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE stakeholder_feedback SET updated_at = NOW() WHERE id = %s::uuid",
                    (feedback_id,),
                )
        conn.rollback()
    finally:
        with conn.cursor() as cur:
            if feedback_id:
                cur.execute("DELETE FROM stakeholder_feedback WHERE id = %s::uuid", (feedback_id,))
        conn.commit()
        conn.close()


def test_buyer_verification_requires_human_party():
    conn = _db()
    try:
        _parties(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM buyer_profile WHERE id = %s::uuid", (BUYER_ID,))
            cur.execute("INSERT INTO buyer_profile (id, name, buyer_type) VALUES (%s::uuid, 'DoD Buyer', 'aggregator')", (BUYER_ID,))
            cur.execute(
                """INSERT INTO party (id, party_type, display_name)
                   VALUES ('b0000000-0000-0000-0000-000000009104'::uuid, 'organization', 'Invalid Verifier')
                   ON CONFLICT (id) DO UPDATE
                   SET party_type = EXCLUDED.party_type,
                       display_name = EXCLUDED.display_name"""
            )
        conn.commit()
        with pytest.raises(Exception, match="human verifier"):
            stakeholder_trust.verify_buyer(
                conn, BUYER_ID, "registration", "registry", verified_by_party_id="b0000000-0000-0000-0000-000000009104"
            )
        conn.rollback()
        verification = stakeholder_trust.verify_buyer(
            conn, BUYER_ID, "registration", "registry", verified_by_party_id=REVIEWER_ID
        )
        assert verification["status"] == "verified"
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM buyer_verification WHERE buyer_id = %s::uuid", (BUYER_ID,))
            cur.execute("DELETE FROM buyer_profile WHERE id = %s::uuid", (BUYER_ID,))
        conn.commit()
        conn.close()


def test_cooperative_governance_links_membership_to_party():
    conn = _db()
    cooperative_id = None
    membership_id = None
    try:
        _parties(conn)
        created = cooperative_service.create_cooperative(
            conn, "DoD Cooperative", "marketing", PILOT_LOCATION,
        )
        cooperative_id = created["cooperative_id"]
        member = cooperative_service.add_member(
            conn, cooperative_id, "F-DOD-MEMBER", party_id=PARTY_ID,
        )
        membership_id = member["member_id"]
        meeting = cooperative_governance.create_meeting(
            conn, cooperative_id, "Annual governance", "annual", "2026-08-01T10:00:00Z",
            created_by_party_id=REVIEWER_ID,
        )
        proposal = cooperative_governance.create_proposal(
            conn, cooperative_id, "Approve market plan", "Approve the reviewed collective market plan.",
            meeting_id=str(meeting["id"]), proposed_by_party_id=PARTY_ID,
        )
        motion = cooperative_governance.create_motion(
            conn, str(proposal["id"]), "approve", "Approve the market plan.",
            moved_by_membership_id=membership_id,
        )
        vote = cooperative_governance.cast_vote(
            conn, str(motion["id"]), membership_id, "for", party_id=PARTY_ID,
        )
        health = cooperative_governance.governance_health(conn, cooperative_id)
        assert vote["vote"] == "for"
        assert health[0]["active_member_count"] == 1
        with conn.cursor() as cur:
            cur.execute("SELECT party_id FROM cooperative_membership WHERE id = %s::uuid", (membership_id,))
            assert str(cur.fetchone()[0]) == PARTY_ID
    finally:
        if cooperative_id:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cooperative WHERE id = %s::uuid", (cooperative_id,))
        conn.commit()
        conn.close()
