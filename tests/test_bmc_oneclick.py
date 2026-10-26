"""Tests for the BMC one-click (create-from-data) capability."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import services.analytics.business_model_canvas as bmc


def _fake_suggest(conn, location_id):
    return {
        "blocks": {
            "key_partners": [{"name": "Coop", "type": "cooperative"}],
            "key_activities": [{"name": "Farming"}],
            "key_resources": [],
            "value_propositions": [],
            "customer_relationships": [],
            "channels": [],
            "customer_segments": [],
            "revenue_streams": [],
            "cost_structure": {},
        },
        "generated_from": ["cooperative"],
    }


def test_create_from_data_populates_blocks():
    created = {"id": "c0000000-0000-0000-0000-00000000000c", "status": "draft", "version": 1}
    conn = MagicMock()
    with patch.object(bmc, "suggest", side_effect=_fake_suggest), \
         patch.object(bmc, "create", return_value=created) as mock_create:
        out = bmc.create_from_data(conn, location_id="a0000000-0000-0000-0000-000000000001")

    assert out["canvas"] == created
    assert out["generated_from"] == ["cooperative"]
    assert "key_partners" in out["populated_blocks"]
    # create() must receive the suggested blocks.
    _, kwargs = mock_create.call_args
    assert kwargs["blocks"]["key_partners"]


def test_create_from_data_requires_entity():
    conn = MagicMock()
    try:
        bmc.create_from_data(conn)
    except ValueError as exc:
        assert "exactly one" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_create_from_data_rejects_ambiguous_scope_before_database_reads():
    conn = MagicMock()
    with patch.object(bmc, "suggest") as mock_suggest, patch.object(bmc, "create") as mock_create:
        try:
            bmc.create_from_data(
                conn,
                location_id="location-1",
                org_id="organization-1",
            )
        except ValueError as exc:
            assert "exactly one" in str(exc)
        else:
            raise AssertionError("expected ValueError")

    mock_suggest.assert_not_called()
    mock_create.assert_not_called()
    conn.rollback.assert_not_called()


class _SuggestionCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        normalized = " ".join(query.split())
        self.connection.queries.append((normalized, params))
        if self.connection.fail_first and "FROM cooperative AS c" in normalized:
            self.connection.fail_first = False
            raise bmc.psycopg2.Error("optional source unavailable")

        fixtures = (
            ("FROM cooperative AS c", [("Kokonut Growers", "cooperative")]),
            ("FROM farm_activity", [("planting", 9)]),
            ("FROM sensor_device AS device", [("Soil probe", "sensor")]),
            ("FROM impact_claim", [("soil_health", "carbon")]),
            ("FROM content_delivery", [("training_app",)]),
            ("FROM buyer_segment", [("Local buyers", "need_based")]),
            ("FROM revenue_event", [("produce_sale", 1200)]),
            ("FROM expense_event", [("seedlings", "DOP", 5000)]),
            ("FROM stakeholder_feedback", [("positive", 5)]),
        )
        self.rows = []
        for marker, rows in fixtures:
            if marker in normalized:
                self.rows = rows
                break
        if "FROM cooperative AS c" in normalized:
            self.rows = [
                ("Kokonut Growers", "cooperative"),
                ("Seed supplier", "supplier"),
            ]
        if "FROM sensor_device AS device" in normalized:
            self.rows = [
                ("Soil probe", "sensor"),
                ("Solar array", "energy"),
                ("Cold room", "shared_asset:storage_facility"),
            ]

    def fetchall(self):
        return self.rows


class _SuggestionConnection:
    def __init__(self, *, fail_first=False):
        self.queries = []
        self.fail_first = fail_first

    def cursor(self):
        return _SuggestionCursor(self)


def test_suggest_uses_only_location_scoped_verified_sources_and_preserves_currency():
    location_id = "a0000000-0000-0000-0000-000000000001"
    conn = _SuggestionConnection()

    result = bmc.suggest(conn, location_id)

    assert result["blocks"]["key_partners"] == [
        {"name": "Kokonut Growers", "type": "cooperative"},
        {"name": "Seed supplier", "type": "supplier"},
    ]
    assert result["blocks"]["key_activities"] == [
        {"name": "planting", "verified_observations": 9}
    ]
    assert result["blocks"]["key_resources"] == [
        {"name": "Soil probe", "type": "sensor"},
        {"name": "Solar array", "type": "energy"},
        {"name": "Cold room", "type": "shared_asset:storage_facility"},
    ]
    assert result["blocks"]["revenue_streams"] == [
        {"type": "produce_sale", "total_usd": 1200.0}
    ]
    assert result["blocks"]["cost_structure"] == {"seedlings": {"DOP": 5000.0}}
    assert result["blocks"]["customer_relationships"] == [
        {"public_feedback_sentiment": {"positive": 5}}
    ]

    selects = [(query, params) for query, params in conn.queries if query.startswith("SELECT")]
    assert len(selects) == 9
    assert all(location_id in params for _query, params in selects)
    joined_sql = " ".join(query for query, _params in selects).lower()
    assert "federation_node" not in joined_sql
    assert "claim_text" not in joined_sql
    assert "stakeholder_name" not in joined_sql
    assert "process_map" not in joined_sql
    assert "count(distinct party_id) >= 5" in joined_sql
    assert "currency" in joined_sql


def test_suggest_optional_source_failure_rolls_back_savepoint_and_continues():
    conn = _SuggestionConnection(fail_first=True)

    result = bmc.suggest(conn, "a0000000-0000-0000-0000-000000000001")

    assert "key_partners" not in result["generated_from"]
    assert "verified_farm_activity" in result["generated_from"]
    statements = [query for query, _params in conn.queries]
    assert "ROLLBACK TO SAVEPOINT bmc_optional_source" in statements
    assert statements.count("RELEASE SAVEPOINT bmc_optional_source") == 9
