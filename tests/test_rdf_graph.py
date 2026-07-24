"""Tests for services.rdf.graph_builder — auto-generate triples from governed records."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_rdf_graph_namespace_helpers():
    from services.rdf.graph_builder import _c, _k, _s

    assert _k("name") == "https://kokonut.network/ontology#name"
    assert _s("name") == "http://schema.org/name"
    assert _c("creditCode") == "https://ontology.commonapproach.org/cids#creditCode"


def test_rdf_graph_build_location_graph_returns_empty_when_missing():
    from services.rdf.graph_builder import build_location_graph

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    result = build_location_graph(conn, "loc-001")
    assert result == []


def test_rdf_graph_build_location_graph_returns_triples():
    from services.rdf.graph_builder import build_location_graph

    conn = MagicMock()
    loc = {
        "name": "Adelphi",
        "description": "Pilot farm",
        "latitude": -1.2,
        "longitude": 36.8,
    }

    # conn.text() is called to build the SQL, then conn.execute() runs it.
    # We intercept at the conn.text level to determine which query.
    text_calls = []
    original_text = conn.text

    def track_text(sql):
        text_calls.append(sql)
        return original_text(sql)

    conn.text = track_text

    def execute_side_effect(*args, **kwargs):
        mock_result = MagicMock()
        sql = text_calls[-1] if text_calls else ""
        if "FROM location" in str(sql):
            mock_result.mappings.return_value.first.return_value = loc
        else:
            mock_result.mappings.return_value.first.return_value = None
        return mock_result

    conn.execute.side_effect = execute_side_effect

    result = build_location_graph(conn, "loc-001")

    assert len(result) >= 3
    predicates = [t["predicate"] for t in result]
    assert "http://schema.org/name" in predicates


def test_rdf_graph_build_credit_graph_returns_empty_when_missing():
    from services.rdf.graph_builder import build_credit_graph

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    result = build_credit_graph(conn, "credit-001")
    assert result == []


def test_rdf_graph_build_credit_graph_returns_triples():
    from services.rdf.graph_builder import build_credit_graph

    credit = {
        "credit_code": "CC-001",
        "vintage_year": 2026,
        "methodology": "IPCC 2006",
        "issuable_tonnes": 100.0,
        "retired_tonnes": 10.0,
        "location_id": "loc-001",
    }
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = credit

    result = build_credit_graph(conn, "credit-001")

    assert len(result) >= 5
    subjects = [t["subject"] for t in result]
    assert all(s.startswith("kokonut:credit:") for s in subjects)


def test_rdf_graph_build_claim_graph_returns_empty_when_missing():
    from services.rdf.graph_builder import build_claim_graph

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    result = build_claim_graph(conn, "claim-001")
    assert result == []


def test_rdf_triple_validation_rejects_incomplete_terms():
    from services.rdf.triple_store import add_triple

    with pytest.raises(ValueError, match="Exactly one"):
        add_triple(MagicMock(), "s", "p")
    with pytest.raises(ValueError, match="Exactly one"):
        add_triple(MagicMock(), "s", "p", object_value="v", object_iri="kokonut:x")


def test_rdf_persist_stages_and_activates_without_deleting():
    from services.rdf import graph_builder

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.side_effect = [
        {"cutoff": "2026-01-01T00:00:00Z"},
        {"id": "generation-1"},
        {"count": 1},
    ]
    with (
        patch.object(
            graph_builder,
            "build_full_graph",
            return_value=[
                {"subject": "s", "predicate": "p", "object_value": "v"},
            ],
        ),
        patch.object(graph_builder, "add_triples", return_value=1),
    ):
        assert graph_builder.persist_graph(conn, "loc-001") == 1
    sql = [call.args[0] for call in conn.text.call_args_list]
    assert not any("DELETE FROM rdf_triple" in statement for statement in sql)
    assert any("rdf_graph_generation" in statement for statement in sql)
    conn.commit.assert_called_once_with()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
