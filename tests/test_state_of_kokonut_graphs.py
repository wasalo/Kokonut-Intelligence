"""Tests for the State of Kokonut visual graph descriptors."""

import json
from unittest import mock

from services.export import kokonut_graphs as kg
from services.export.report_generator import REPORT_GENERATORS, generate_state_of_kokonut_graphs


def _fake_conn(rows_by_query=None):
    """Build a cursor-returning fake connection for the builders."""
    rows_by_query = rows_by_query or {}

    def _execute(query, params=None):
        # Match on a substring so we can route the right fixture.
        for key, rows in rows_by_query.items():
            if key in query:
                _execute.result = rows
                return
        _execute.result = []

    def _fetchall():
        return _execute.result

    cur = mock.MagicMock()
    cur.execute.side_effect = _execute
    cur.fetchall.side_effect = _fetchall
    conn = mock.MagicMock()
    conn.cursor.return_value = cur
    return conn


def test_registered():
    assert "state_of_kokonut_graphs" in REPORT_GENERATORS


def test_ecosystem_tree_structure():
    conn = _fake_conn({
        "FROM funding_round": [
            {"id": _uuid(), "round_name": "Seed", "actor_type": "network",
             "period_start": "2021-06-01", "raised_amount": 1000, "currency": "USD"},
        ],
        "FROM dao_proposal": [],
    })
    desc = kg.build_ecosystem_tree(conn, "2021-01-01", "2024-12-31")
    assert desc.layout == "tree"
    assert any(n.kind == "year" for n in desc.nodes)
    assert any(n.kind == "round" for n in desc.nodes)
    mermaid = desc.to_mermaid()
    assert mermaid.startswith("flowchart TD")
    assert "Y2021" in mermaid


def test_ikigai_v2_has_growth_and_ring():
    conn = _fake_conn({"FROM funding_round": []})
    desc = kg.build_ikigai_circular(conn, "2021-01-01", "2024-12-31", version=2)
    assert any(n.kind == "ring" for n in desc.nodes)
    assert any(n.kind == "growth" for n in desc.nodes)
    assert any(e.kind == "growth" for e in desc.edges)
    mermaid = desc.to_mermaid()
    assert "Ready for Growth" in mermaid
    assert "RING" in mermaid


def test_ikigai_v1_no_growth():
    conn = _fake_conn({"FROM funding_round": []})
    desc = kg.build_ikigai_circular(conn, "2021-01-01", "2024-12-31", version=1)
    assert not any(n.kind == "ring" for n in desc.nodes)
    assert not any(n.kind == "growth" for n in desc.nodes)


def test_descriptor_json_serializable():
    conn = _fake_conn({"FROM funding_round": []})
    desc = kg.build_ikigai_circular(conn)
    payload = desc.to_json()
    # Must round-trip through json.dumps (no non-serializable values).
    json.dumps(payload)
    assert payload["layout"] == "circular"


def test_generate_state_of_kokonut_graphs_isolates_errors():
    # A builder that raises should be isolated, not break the whole report.
    conn = _fake_conn({"FROM funding_round": []})
    report = generate_state_of_kokonut_graphs(conn, location_id="all")
    assert report["report_type"] == "state_of_kokonut_graphs"
    assert isinstance(report["graphs"], list)
    assert all("name" in g for g in report["graphs"])


def test_farm_phases_requires_location_data():
    conn = _fake_conn({
        "SELECT name FROM location": [{"name": "Adelphi"}],
        "FROM farm_zone": [
            {"id": _uuid(), "name": "Nursery", "zone_type": "nursery", "status": "active"},
        ],
    })
    desc = kg.build_farm_phases(conn, "00000000-0000-0000-0000-000000000001")
    assert desc.layout == "tree"
    assert any(n.kind == "zone" for n in desc.nodes)
    assert desc.to_mermaid().startswith("flowchart TD")


def _uuid():
    import uuid
    return uuid.uuid4()
