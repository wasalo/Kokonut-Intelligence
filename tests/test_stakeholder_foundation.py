"""Integration tests for the canonical stakeholder foundation."""

import pytest

from services.analytics import stakeholders
from services.export.report_generator import generate_stakeholder_landscape
from services.ingestion.base import get_db


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_party_relationship_interest_and_salience_lifecycle():
    conn = _db()
    party_id = None
    other_party_id = None
    try:
        party = stakeholders.create_party(
            conn, "community", "Test stakeholder community", privacy_level="limited"
        )
        party_id = party["id"]
        other_party = stakeholders.create_party(conn, "organization", "Test steward")
        other_party_id = other_party["id"]

        identifier = stakeholders.add_identifier(
            conn, party_id, "external_id", "community-test-1", "test", confidence=0.6
        )
        relationship = stakeholders.link_parties(
            conn, other_party_id, party_id, "supports", legitimacy="derivative", confidence=0.8
        )
        interest = stakeholders.add_interest(
            conn, party_id, "need", "Accessible participation", priority=5,
            legitimacy="normative", scope_type="location",
        )
        assessment = stakeholders.assess_salience(
            conn, party_id, interest_id=interest["id"], power=2,
            legitimacy=9, urgency=7, vulnerability=8, harm_exposure=9,
            representation=2, rationale="Low power does not remove legitimate high-harm exposure.",
        )

        detail = stakeholders.get_party(conn, party_id)
        assert identifier["verification_status"] == "candidate"
        assert relationship["status"] == "proposed"
        assert detail["identifiers"][0]["id"] == identifier["id"]
        assert detail["relationships"][0]["from_party_id"] == other_party_id
        assert detail["interests"][0]["id"] == interest["id"]
        assert float(assessment["advisory_score"]) > 6
    finally:
        if party_id:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM party WHERE id IN (%s::uuid, %s::uuid)", (party_id, other_party_id))
            conn.commit()
        conn.close()


def test_seeded_proxy_parties_and_landscape_report():
    conn = _db()
    try:
        landscape = stakeholders.list_landscape(conn)
        names = {row["display_name"] for row in landscape}
        assert "Adelphi living systems" in names
        assert "Future generations" in names

        report = generate_stakeholder_landscape(conn)
        assert report["report_type"] == "stakeholder_landscape"
        assert report["party_count"] >= 5
        assert any(row["open_interest_count"] > 0 for row in report["parties"])
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM v_stakeholder_source_candidates")
            assert cur.fetchone()[0] >= 0
    finally:
        conn.close()


def test_party_type_validation():
    conn = _db()
    try:
        with pytest.raises(ValueError, match="party_type"):
            stakeholders.create_party(conn, "shareholder", "Invalid party")
    finally:
        conn.close()
