"""Unit tests for Linked Data, IRI, Credit Class, RDF, Certificates, and Metadata API."""

from __future__ import annotations

import hashlib
import json
import uuid
from unittest.mock import MagicMock

import pytest


def _fake_conn(rows=None, rowcount=1):
    conn = MagicMock()
    result = MagicMock()
    mappings_result = MagicMock()
    if rows is None:
        rows = []
    elif isinstance(rows, dict):
        rows = [rows]
    mappings_result.all.return_value = rows
    mappings_result.first.return_value = rows[0] if rows else None
    mappings_result.__iter__ = lambda self: iter(rows)
    result.mappings.return_value = mappings_result
    result.rowcount = rowcount
    conn.execute.return_value = result
    conn.text = lambda sql: sql
    return conn


def _fake_conn_sequential(responses, rowcount=1):
    """Create a mock that returns different data for each execute() call."""
    conn = MagicMock()
    call_count = [0]

    def make_result(rows):
        result = MagicMock()
        mappings_result = MagicMock()
        if rows is None:
            rows = []
        elif isinstance(rows, dict):
            rows = [rows]
        mappings_result.all.return_value = rows
        mappings_result.first.return_value = rows[0] if rows else None
        mappings_result.__iter__ = lambda self: iter(rows)
        result.mappings.return_value = mappings_result
        result.rowcount = rowcount
        return result

    def execute_side_effect(*args, **kwargs):
        idx = min(call_count[0], len(responses) - 1)
        call_count[0] += 1
        return make_result(responses[idx])

    conn.execute = MagicMock(side_effect=execute_side_effect)
    conn.text = lambda sql: sql
    return conn


LOCATION_ID = str(uuid.uuid4())
CLASS_ID = str(uuid.uuid4())
BATCH_ID = str(uuid.uuid4())
CREDIT_ID = str(uuid.uuid4())
CLAIM_ID = str(uuid.uuid4())
RETIREMENT_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# IRI Resolver tests
# ---------------------------------------------------------------------------

class TestIRIResolver:
    def test_generate_iri(self):
        from services.iri.resolver import generate_iri
        conn = _fake_conn(rows=[{"max_version": None}], rowcount=1)
        iri = generate_iri(conn, "location", LOCATION_ID, content={"name": "Test"})
        assert iri.startswith("kokonut:location:")
        assert "v1" in iri

    def test_resolve_iri_found(self):
        from services.iri.resolver import resolve_iri
        conn = _fake_conn(rows={"iri": "kokonut:location:UUID:v1", "entity_type": "location"})
        result = resolve_iri(conn, "kokonut:location:UUID:v1")
        assert result is not None

    def test_resolve_iri_not_found(self):
        from services.iri.resolver import resolve_iri
        conn = _fake_conn(rows=[])
        result = resolve_iri(conn, "nonexistent")
        assert result is None

    def test_get_current_iri(self):
        from services.iri.resolver import get_current_iri
        conn = _fake_conn(rows={"iri": "kokonut:location:UUID:v2"})
        iri = get_current_iri(conn, "location", LOCATION_ID)
        assert iri == "kokonut:location:UUID:v2"

    def test_get_version_history(self):
        from services.iri.resolver import get_version_history
        conn = _fake_conn(rows=[
            {"iri": "kokonut:location:UUID:v1", "version": 1, "is_current": False},
            {"iri": "kokonut:location:UUID:v2", "version": 2, "is_current": True},
        ])
        history = get_version_history(conn, "location", LOCATION_ID)
        assert len(history) == 2


# ---------------------------------------------------------------------------
# IRI Versioning tests
# ---------------------------------------------------------------------------

class TestIRIVersioning:
    def test_create_version(self):
        from services.iri.versioning import create_version
        conn = _fake_conn_sequential([
            {"max_version": 1},      # MAX(version) query
            {"iri": "kokonut:location:UUID:v1"},  # previous version query
            {"id": str(uuid.uuid4())},  # INSERT
        ])
        iri = create_version(conn, "location", LOCATION_ID, {"name": "Updated"})
        assert "v2" in iri


# ---------------------------------------------------------------------------
# Credit Class tests
# ---------------------------------------------------------------------------

class TestCreditClass:
    def test_create_class(self):
        from services.credit_class.class_manager import create_class
        conn = _fake_conn(rows={"id": CLASS_ID})
        result = create_class(conn, name="Kokonut Carbon", methodology="IPCC 2006", credit_type="carbon",
                              url="https://example.com/class", primary_impact_type="carbon",
                              primary_impact_name="Carbon Sequestration", primary_impact_sdgs=[13, 15])
        assert result["id"] == CLASS_ID

    def test_create_class_invalid_type(self):
        from services.credit_class.class_manager import create_class
        conn = _fake_conn()
        with pytest.raises(ValueError, match="Invalid credit_type"):
            create_class(conn, name="X", methodology="M", credit_type="invalid")

    def test_list_classes(self):
        from services.credit_class.class_manager import list_classes
        conn = _fake_conn(rows=[{"name": "Test", "credit_type": "carbon", "status": "published"}])
        classes = list_classes(conn)
        assert len(classes) == 1

    def test_get_class_full(self):
        from services.credit_class.class_manager import get_class_full
        conn = _fake_conn_sequential([
            {"id": CLASS_ID, "name": "Test", "url": "https://example.com"},  # get_class
            [{"impact_name": "Biodiversity"}],  # cobenefits
            [{"registry_name": "Verra"}],  # registries
            [{"name": "CDM"}],  # programs
            [{"name": "Protocol v1"}],  # protocols
            [{"name": "Methodology A"}],  # methodologies
            [{"name": "Pool 1"}],  # buffer_pools
        ])
        result = get_class_full(conn, CLASS_ID)
        assert result is not None
        assert result["url"] == "https://example.com"
        assert len(result["cobenefits"]) == 1
        assert len(result["registries"]) == 1


# ---------------------------------------------------------------------------
# Credit Batch tests
# ---------------------------------------------------------------------------

class TestCreditBatch:
    def test_create_batch(self):
        from services.credit_class.batch_manager import create_batch
        conn = _fake_conn_sequential([
            {"id": CLASS_ID, "methodology": "IPCC", "name": "Kokonut Carbon"},  # get_class_with_validation
            {"methodology": "IPCC"},  # _generate_batch_code: methodology query
            {"name": "Adelphi"},  # _generate_batch_code: location query
            {"seq": 1},  # _generate_batch_code: sequence query
            {"id": BATCH_ID},  # INSERT result
        ])
        result = create_batch(conn, credit_class_id=CLASS_ID, location_id=LOCATION_ID, vintage_year=2026, total_quantity=100)
        assert "batch_code" in result

    def test_get_batch_balance(self):
        from services.credit_class.batch_manager import get_batch_balance
        conn = _fake_conn(rows={
            "batch_code": "CC-IPC-2026-ADEL-0001",
            "total_quantity": 100, "issued_quantity": 100,
            "retired_quantity": 20, "cancelled_quantity": 0,
            "available_quantity": 80, "unit": "tonneCO2e",
        })
        balance = get_batch_balance(conn, BATCH_ID)
        assert balance["available_quantity"] == 80


# ---------------------------------------------------------------------------
# Credit Class Entity tests
# ---------------------------------------------------------------------------

class TestCreditClassEntities:
    def test_add_cobenefit(self):
        from services.credit_class.entities import add_cobenefit
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_cobenefit(conn, CLASS_ID, "Biodiversity", impact_type="co_benefit", sdg_numbers=[15])
        assert "id" in result

    def test_list_cobenefits(self):
        from services.credit_class.entities import list_cobenefits
        conn = _fake_conn(rows=[{"impact_name": "Biodiversity", "impact_type": "co_benefit"}])
        items = list_cobenefits(conn, CLASS_ID)
        assert len(items) == 1

    def test_add_registry(self):
        from services.credit_class.entities import add_registry
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_registry(conn, CLASS_ID, "Verra", registry_url="https://verra.org")
        assert "id" in result

    def test_add_program(self):
        from services.credit_class.entities import add_program
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_program(conn, CLASS_ID, "VCS", url="https://verra.org/vcs")
        assert "id" in result

    def test_add_protocol(self):
        from services.credit_class.entities import add_protocol
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_protocol(conn, CLASS_ID, "IPCC 2006 Tier 2", is_primary=True)
        assert "id" in result

    def test_add_methodology(self):
        from services.credit_class.entities import add_methodology
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_methodology(conn, CLASS_ID, "VM0042", url="https://verra.org/vm0042")
        assert "id" in result

    def test_add_buffer_pool(self):
        from services.credit_class.entities import add_buffer_pool
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_buffer_pool(conn, CLASS_ID, "Kokonut Pool", wallet_address="0x1234")
        assert "id" in result

    def test_delete_cobenefit(self):
        from services.credit_class.entities import delete_cobenefit
        conn = _fake_conn(rowcount=1)
        assert delete_cobenefit(conn, str(uuid.uuid4())) is True


# ---------------------------------------------------------------------------
# RDF Triple Store tests
# ---------------------------------------------------------------------------

class TestRDFTripleStore:
    def test_add_triple(self):
        from services.rdf.triple_store import add_triple
        conn = _fake_conn(rowcount=1)
        result = add_triple(conn, "s1", "p1", object_value="o1", graph_name="test")
        assert result["subject"] == "s1"

    def test_count_triples(self):
        from services.rdf.triple_store import count_triples
        conn = _fake_conn(rows={"cnt": 42})
        count = count_triples(conn)
        assert count == 42

    def test_query_triples(self):
        from services.rdf.triple_store import query_triples
        conn = _fake_conn(rows=[{"subject": "s1", "predicate": "p1", "object_value": "o1"}])
        results = query_triples(conn, subject="s1")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# RDF Serializers tests
# ---------------------------------------------------------------------------

class TestRDFSerializers:
    def test_to_ntriples(self):
        from services.rdf.serializers import to_ntriples
        triples = [{"subject": "s1", "predicate": "p1", "object_value": "hello"}]
        nt = to_ntriples(triples)
        assert "<s1> <p1> \"hello\" ." in nt

    def test_to_turtle(self):
        from services.rdf.serializers import to_turtle
        triples = [{"subject": "s1", "predicate": "p1", "object_value": "hello"}]
        ttl = to_turtle(triples, namespaces={"ex": "http://example.org/"})
        assert "@prefix ex:" in ttl

    def test_to_jsonld(self):
        from services.rdf.serializers import to_jsonld
        triples = [{"subject": "s1", "predicate": "http://schema.org/name", "object_value": "Test"}]
        doc = to_jsonld(triples)
        assert "@graph" in doc
        assert len(doc["@graph"]) == 1

    def test_from_jsonld(self):
        from services.rdf.serializers import from_jsonld
        doc = {"@graph": [{"@id": "s1", "name": "Test", "link": {"@id": "s2"}}]}
        triples = from_jsonld(doc)
        assert len(triples) >= 2


# ---------------------------------------------------------------------------
# RDF Graph Builder tests
# ---------------------------------------------------------------------------

class TestRDFGraphBuilder:
    def test_build_location_graph(self):
        from services.rdf.graph_builder import build_location_graph
        conn = _fake_conn(rows={"id": LOCATION_ID, "name": "Adelphi", "latitude": 18.5, "longitude": -69.9})
        triples = build_location_graph(conn, LOCATION_ID)
        assert len(triples) >= 2


# ---------------------------------------------------------------------------
# SPARQL Engine tests
# ---------------------------------------------------------------------------

class TestSPARQLEngine:
    def test_parse_select_query(self):
        from services.rdf.sparql_engine import parse_select_query
        query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o . } LIMIT 10"
        parsed = parse_select_query(query)
        assert len(parsed["variables"]) == 3
        assert parsed["limit"] == 10

    def test_list_named_graphs(self):
        from services.rdf.sparql_engine import list_named_graphs
        conn = _fake_conn(rows=[{"name": "location:adelphi", "triple_count": 50}])
        graphs = list_named_graphs(conn)
        assert len(graphs) == 1


# ---------------------------------------------------------------------------
# Certificate tests
# ---------------------------------------------------------------------------

class TestCertificates:
    def test_render_certificate_html(self):
        from services.certificates.generator import render_certificate_html
        html = render_certificate_html({
            "certificate_number": "RET-2026-ADEL-0001",
            "beneficiary_name": "Test Corp",
            "retired_tonnes": "10.5",
            "vintage_year": "2026",
            "methodology": "IPCC 2006",
            "retirement_reason": "voluntary_retirement",
            "retirement_statement": "Offsetting emissions",
            "issued_at": "2026-07-11",
            "verification_url": "https://kokonut.network/certificate/RET-2026-ADEL-0001",
        })
        assert "RET-2026-ADEL-0001" in html
        assert "Test Corp" in html
        assert "10.5" in html


# ---------------------------------------------------------------------------
# LinkML tests
# ---------------------------------------------------------------------------

class TestLinkML:
    def test_register_schema(self):
        from services.linkml.validator import register_schema
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = register_schema(conn, "test_schema", "1.0", "classes:\n  Test:\n    attributes:\n      name:\n        required: true")
        assert result["name"] == "test_schema"

    def test_list_schemas(self):
        from services.linkml.validator import list_schemas
        conn = _fake_conn(rows=[{"name": "test", "version": "1.0", "status": "active"}])
        schemas = list_schemas(conn)
        assert len(schemas) == 1


# ---------------------------------------------------------------------------
# App Metadata tests
# ---------------------------------------------------------------------------

class TestAppMetadata:
    def test_get_app_metadata(self):
        from services.metadata_api.app_metadata import get_app_metadata
        conn = _fake_conn(rows={"location_id": LOCATION_ID, "tagline": "Test Farm"})
        result = get_app_metadata(conn, LOCATION_ID)
        assert result["tagline"] == "Test Farm"

    def test_get_complete_project_view(self):
        from services.metadata_api.app_metadata import get_complete_project_view
        conn = _fake_conn_sequential([
            {"id": LOCATION_ID, "name": "Adelphi", "latitude": 18.5, "longitude": -69.9},  # location
            None,  # registry
            [],  # links
            [],  # reference_ids
            None,  # app_metadata
            {"iri": "kokonut:location:UUID:v1"},  # get_current_iri
        ])
        view = get_complete_project_view(conn, LOCATION_ID)
        assert view["name"] == "Adelphi"
        assert view["latitude"] == 18.5


# ---------------------------------------------------------------------------
# Project Info tests
# ---------------------------------------------------------------------------

class TestProjectInfo:
    def test_add_project_link(self):
        from services.metadata_api.project_info import add_project_link
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_project_link(conn, LOCATION_ID, "Website", "https://example.com")
        assert "id" in result

    def test_list_project_links(self):
        from services.metadata_api.project_info import list_project_links
        conn = _fake_conn(rows=[{"link_name": "Website", "link_url": "https://example.com"}])
        links = list_project_links(conn, LOCATION_ID)
        assert len(links) == 1

    def test_delete_project_link(self):
        from services.metadata_api.project_info import delete_project_link
        conn = _fake_conn(rowcount=1)
        assert delete_project_link(conn, str(uuid.uuid4())) is True

    def test_add_project_reference_id(self):
        from services.metadata_api.project_info import add_project_reference_id
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_project_reference_id(conn, LOCATION_ID, "VCS-1234", "verra", registry_name="Verra")
        assert "id" in result

    def test_list_project_reference_ids(self):
        from services.metadata_api.project_info import list_project_reference_ids
        conn = _fake_conn(rows=[{"identifier": "VCS-1234", "reference_type": "verra"}])
        refs = list_project_reference_ids(conn, LOCATION_ID)
        assert len(refs) == 1

    def test_get_project_info(self):
        from services.metadata_api.project_info import get_project_info
        conn = _fake_conn_sequential([
            {"id": LOCATION_ID, "name": "Adelphi", "project_url": "https://example.com",
             "project_start_date": "2026-01-01", "bioregion": ["Caribbean"],
             "biome_type": ["tropical"], "watershed": "Rio Yuna"},  # location
            None,  # registry
            [],  # links
            [],  # reference_ids
            None,  # app_metadata
            {"iri": "kokonut:location:UUID:v1"},  # get_current_iri
        ])
        info = get_project_info(conn, LOCATION_ID)
        assert info["name"] == "Adelphi"
        assert info["url"] == "https://example.com"
        assert info["bioregion"] == ["Caribbean"]
        assert info["watershed"] == "Rio Yuna"


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------

class TestLinkedDataSafety:
    def test_credit_class_in_governed(self):
        from services.agents.safety import GOVERNED_COLLECTIONS
        assert "credit_class" in GOVERNED_COLLECTIONS

    def test_credit_batch_in_governed(self):
        from services.agents.safety import GOVERNED_COLLECTIONS
        assert "credit_batch" in GOVERNED_COLLECTIONS

    def test_retirement_certificate_in_governed(self):
        from services.agents.safety import GOVERNED_COLLECTIONS
        assert "retirement_certificate" in GOVERNED_COLLECTIONS

    def test_iri_registry_in_governed(self):
        from services.agents.safety import GOVERNED_COLLECTIONS
        assert "iri_registry" in GOVERNED_COLLECTIONS

    def test_app_project_metadata_in_governed(self):
        from services.agents.safety import GOVERNED_COLLECTIONS
        assert "app_project_metadata" in GOVERNED_COLLECTIONS
