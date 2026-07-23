"""Tests for services.rdf.sparql_engine — SPARQL-to-SQL translation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_sparql_engine_parse_simple_select():
    from services.rdf.sparql_engine import parse_select_query

    query = 'SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 100'
    result = parse_select_query(query)

    assert result["variables"] == ["s", "p", "o"]
    assert len(result["patterns"]) == 1
    assert result["limit"] == 100


def test_sparql_engine_parse_rejects_non_select():
    from services.rdf.sparql_engine import parse_select_query

    with pytest.raises(ValueError, match="Only SELECT"):
        parse_select_query("INSERT INTO foo VALUES (1)")


def test_sparql_engine_parse_rejects_duplicate_variables():
    from services.rdf.sparql_engine import parse_select_query

    with pytest.raises(ValueError, match="unique"):
        parse_select_query('SELECT ?s ?s ?o WHERE { ?s ?p ?o }')


def test_sparql_engine_parse_enforces_limit_cap():
    from services.rdf.sparql_engine import parse_select_query

    result = parse_select_query('SELECT ?s WHERE { ?s ?p ?o } LIMIT 99999')
    assert result["limit"] == 1000


def test_sparql_engine_parse_iri_in_triple():
    from services.rdf.sparql_engine import parse_select_query

    query = 'SELECT ?o WHERE { <https://example.org/s> <https://example.org/p> ?o }'
    result = parse_select_query(query)

    assert len(result["patterns"]) == 1
    assert result["patterns"][0]["subject"] == "https://example.org/s"
    assert result["patterns"][0]["subject_is_var"] is False


def test_sparql_engine_translate_generates_sql():
    from services.rdf.sparql_engine import translate_basic_graph_pattern, parse_select_query

    query = 'SELECT ?s ?o WHERE { ?s <http://schema.org/name> ?o }'
    parsed = parse_select_query(query)
    sql = translate_basic_graph_pattern(parsed["patterns"], parsed["variables"])

    assert "SELECT" in sql
    assert "rdf_triple" in sql
    assert "WHERE" in sql


def test_sparql_engine_translate_multiple_patterns():
    from services.rdf.sparql_engine import translate_basic_graph_pattern, parse_select_query

    query = 'SELECT ?name ?type WHERE { ?s <http://schema.org/name> ?name . ?s <http://schema.org/type> ?type }'
    parsed = parse_select_query(query)
    sql = translate_basic_graph_pattern(parsed["patterns"], parsed["variables"])

    assert sql.count("rdf_triple") == 2


def test_sparql_engine_term_sql_object():
    from services.rdf.sparql_engine import _term_sql

    val_sql, kind_sql = _term_sql("t0", "object")
    assert "COALESCE" in val_sql
    assert "object_iri" in val_sql


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
