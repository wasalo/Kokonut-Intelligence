"""JSON-LD namespace and context regression tests."""

from services.linkml.jsonld import (
    DEFAULT_CONTEXT,
    compact_uri,
    expand_prefixed_term,
    generate_context,
    to_jsonld_document,
    to_jsonld_with_graph,
)


def test_default_context_matches_repository_linkml_prefixes():
    assert DEFAULT_CONTEXT["schema"] == "http://schema.org/"
    assert DEFAULT_CONTEXT["geo"] == "http://www.opengis.net/ont/geosparql#"


def test_schema_and_geosparql_terms_expand_to_declared_uris():
    assert expand_prefixed_term("schema:name") == "http://schema.org/name"
    assert expand_prefixed_term("geo:hasGeometry") == (
        "http://www.opengis.net/ont/geosparql#hasGeometry"
    )


def test_compact_uri_round_trips_repository_vocabulary():
    for term in ("schema:name", "geo:hasGeometry", "rfs:hasFeature", "kokonut:Project"):
        expanded = expand_prefixed_term(term)
        assert compact_uri(expanded) == term


def test_prefix_helpers_respect_an_explicit_empty_context():
    assert expand_prefixed_term("schema:name", {}) == "schema:name"
    assert compact_uri("http://schema.org/name", {}) == "http://schema.org/name"


def test_generate_context_keeps_schema_and_geo_uri_mappings():
    context = generate_context("Project", {"projectSize": "rfs:projectSize"})

    assert context["schema"] == "http://schema.org/"
    assert context["geo"] == "http://www.opengis.net/ont/geosparql#"
    assert context["projectSize"] == "rfs:projectSize"
    assert context is not DEFAULT_CONTEXT


def test_jsonld_document_preserves_an_explicit_empty_context():
    document = to_jsonld_document("Project", {"name": "Genesis"}, context={})

    assert document["@context"] == {}


def test_jsonld_graph_preserves_an_explicit_empty_context():
    document = to_jsonld_with_graph([{"@type": "kokonut:Project", "name": "Genesis"}], context={})

    assert document["@context"] == {}

