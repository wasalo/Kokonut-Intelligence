"""Integration tests for the canonical stakeholder foundation."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from services.analytics import stakeholders
from services.export.report_generator import (
    generate_stakeholder_decision_lineage,
    generate_stakeholder_engagement,
    generate_stakeholder_grievance,
    generate_stakeholder_landscape,
)
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
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM location ORDER BY id LIMIT 1")
            location_id = cur.fetchone()[0]
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
            legitimacy="normative", scope_type="location", scope_id=str(location_id),
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
        conn.rollback()
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

        with conn.cursor() as cur:
            cur.execute("SELECT id FROM location WHERE slug = 'kokonut-adelphi'")
            location_row = cur.fetchone()
        assert location_row is not None
        report = generate_stakeholder_landscape(conn, location_id=str(location_row[0]))
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


def test_create_party_rejects_invalid_privacy_level():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="privacy_level"):
        stakeholders.create_party(mock_conn, "person", "Test", privacy_level="world_visible")


def test_add_interest_rejects_invalid_interest_type():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="interest_type"):
        stakeholders.add_interest(mock_conn, "p1", "invalid_type", "Title")


def test_assess_salience_rejects_out_of_range_score():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="scores must be between 0 and 10"):
        stakeholders.assess_salience(mock_conn, "p1", power=11, rationale="Test")


def _landscape_report_connection(rows):
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = None
    cursor.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


def test_location_landscape_uses_location_lineage_view():
    row = {"location_id": "location-a", "party_id": "party-a", "active_relationship_count": 1}
    conn, cursor = _landscape_report_connection([row])

    report = generate_stakeholder_landscape(conn, location_id="location-a")

    assert report["parties"] == [row]
    assert report["party_count"] == 1
    assert "v_stakeholder_landscape_by_location" in cursor.execute.call_args.args[0]
    assert "location_id = %s::uuid" in cursor.execute.call_args.args[0]
    assert "v_stakeholder_landscape " not in cursor.execute.call_args.args[0]
    assert cursor.execute.call_args.args[1] == ["location-a"]
    assert any("explicit location lineage" in item for item in report["limitations"])


@pytest.mark.parametrize(
    ("report_type", "generator"),
    [
        ("stakeholder_landscape", generate_stakeholder_landscape),
        ("stakeholder_engagement", generate_stakeholder_engagement),
        ("stakeholder_grievance", generate_stakeholder_grievance),
        ("stakeholder_decision_lineage", generate_stakeholder_decision_lineage),
    ],
)
def test_stakeholder_reports_reject_missing_location_before_database_access(
    report_type, generator
):
    conn = MagicMock()

    with pytest.raises(ValueError, match=f"{report_type} requires an explicit location_id"):
        generator(conn)

    conn.cursor.assert_not_called()


def test_location_landscape_aggregates_only_explicit_location_lineage():
    conn = _db()
    party_ids = [str(uuid4()) for _ in range(3)]
    relationship_ids = [str(uuid4()) for _ in range(3)]
    interest_ids = [str(uuid4()) for _ in range(3)]
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM location ORDER BY id LIMIT 2")
            locations = [str(row[0]) for row in cur.fetchall()]
        if len(locations) < 2:
            pytest.skip("location-scoped stakeholder landscape needs two locations")

        shared_party, first_neighbor, second_neighbor = party_ids
        first_location, second_location = locations
        with conn.cursor() as cur:
            for party_id, display_name in zip(
                party_ids,
                ("Synthetic shared party", "Synthetic first neighbor", "Synthetic second neighbor"),
            ):
                cur.execute(
                    "INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'organization', %s)",
                    (party_id, display_name),
                )
            for location_id in locations:
                cur.execute(
                    """INSERT INTO party_identifier
                       (party_id, identifier_type, identifier_value, source_system, verification_status)
                       VALUES (%s::uuid, 'location_id', %s, 'stakeholder-landscape-scope-test', 'verified')""",
                    (shared_party, location_id),
                )
            cur.execute(
                """INSERT INTO party_identifier
                   (party_id, identifier_type, identifier_value, source_system, verification_status)
                       VALUES (%s::uuid, 'location_id', %s, 'stakeholder-landscape-candidate-scope-test', 'candidate')""",
                (first_neighbor, first_location),
            )
            for relationship_id, neighbor, location_id, scope_type in (
                (relationship_ids[0], first_neighbor, first_location, "location"),
                (relationship_ids[1], second_neighbor, second_location, "location"),
                (relationship_ids[2], first_neighbor, None, "network"),
            ):
                cur.execute(
                    """INSERT INTO party_relationship
                       (id, from_party_id, to_party_id, relationship_type, scope_type, scope_id, status)
                       VALUES (%s::uuid, %s::uuid, %s::uuid, 'synthetic_support', %s, %s::uuid, 'active')""",
                    (relationship_id, shared_party, neighbor, scope_type, location_id),
                )
            for interest_id, location_id in zip(interest_ids, (first_location, second_location, None)):
                scope_type = "location" if location_id else "network"
                cur.execute(
                    """INSERT INTO stakeholder_interest
                       (id, party_id, interest_type, title, scope_type, scope_id, status)
                       VALUES (%s::uuid, %s::uuid, 'need', 'Synthetic scoped interest', %s, %s::uuid, 'validated')""",
                    (interest_id, shared_party, scope_type, location_id),
                )
            for interest_id, scores in zip(interest_ids, (10, 0, 5)):
                cur.execute(
                    """INSERT INTO stakeholder_salience_assessment
                       (party_id, interest_id, power_score, legitimacy_score, urgency_score,
                        vulnerability_score, harm_exposure_score, representation_score, rationale)
                       VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s,
                               'Synthetic location-scope regression')""",
                    (shared_party, interest_id, scores, scores, scores, scores, scores, scores),
                )

            results = {}
            for location_id in locations:
                cur.execute(
                    """SELECT identifier_count, active_relationship_count, open_interest_count,
                              advisory_score
                       FROM v_stakeholder_landscape_by_location
                       WHERE location_id = %s::uuid AND party_id = %s::uuid""",
                    (location_id, shared_party),
                )
                results[location_id] = cur.fetchone()
            cur.execute(
                """SELECT identifier_count FROM v_stakeholder_landscape_by_location
                   WHERE location_id = %s::uuid AND party_id = %s::uuid""",
                (first_location, first_neighbor),
            )
            candidate_identifier_count = cur.fetchone()[0]
            cur.execute(
                """SELECT reloptions FROM pg_class
                   WHERE oid = 'v_stakeholder_landscape_by_location'::regclass"""
            )
            view_options = cur.fetchone()[0]

        assert results[first_location] == (1, 1, 1, 9)
        assert results[second_location] == (1, 1, 1, 1)
        assert candidate_identifier_count == 0
        assert "security_invoker=true" in view_options
    finally:
        conn.rollback()
        conn.close()


def test_assess_salience_rejects_empty_rationale():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="rationale is required"):
        stakeholders.assess_salience(mock_conn, "p1", rationale="  ")


def test_link_parties_rejects_invalid_legitimacy():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="legitimacy"):
        stakeholders.link_parties(mock_conn, "p1", "p2", "supports", legitimacy="invalid")
