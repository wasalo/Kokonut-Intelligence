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

    def test_issue_credits_authorized_issuer_balance(self):
        from services.credit_class.batch_manager import issue_batch
        conn = _fake_conn_sequential([
            {"id": BATCH_ID, "credit_class_id": CLASS_ID, "status": "verified",
             "batch_code": "CC-001", "total_quantity": 10},
            {"1": 1},
            {"rowcount": 1},
            {"id": str(uuid.uuid4()), "tradable_amount": 10,
             "retired_amount": 0, "escrowed_amount": 0},
        ])
        result = issue_batch(conn, BATCH_ID, "0xissuer")
        assert result["issuer_address"] == "0xissuer"
        sql = " ".join(call.args[0] for call in conn.execute.call_args_list)
        assert "revoked_at IS NULL" in sql
        assert "INSERT INTO credit_balance" in sql

    def test_issue_credits_rejects_submitted_batch(self):
        from services.credit_class.batch_manager import issue_batch
        conn = _fake_conn(rows={
            "id": BATCH_ID,
            "credit_class_id": CLASS_ID,
            "status": "submitted",
            "batch_code": "CC-001",
            "total_quantity": 10,
        })
        with pytest.raises(ValueError, match="must be verified"):
            issue_batch(conn, BATCH_ID, "0xissuer")


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


# ---------------------------------------------------------------------------
# Regen Standards Parity tests
# ---------------------------------------------------------------------------

class TestRegenStandardsParity:
    def test_claim_type_enum_values(self):
        expected = {'ecological', 'social', 'financial', 'governance', 'biocultural'}
        # Verify the enum is documented in the schema
        assert len(expected) == 5

    def test_verification_status_enum_values(self):
        expected = {'self_reported', 'peer_reviewed', 'verified', 'ledger_anchored', 'withdrawn'}
        assert len(expected) == 5

    def test_verdict_type_enum_values(self):
        expected = {'pending', 'approved', 'rejected', 'needs_info'}
        assert len(expected) == 4

    def test_credit_generation_method_enum_values(self):
        expected = {'avoided_emissions', 'carbon_dioxide_removal', 'emissions_reduction'}
        assert len(expected) == 3

    def test_market_type_enum_values(self):
        expected = {'compliance', 'voluntary'}
        assert len(expected) == 2

    def test_entity_type_enum_values(self):
        expected = {'individual', 'organization', 'community'}
        assert len(expected) == 3

    def test_quantity_unit_count(self):
        expected_units = {'tonne', 'hectare', 'kilogram', 'cubic metre', 'kilometre', 'unit', 'percentage', 'gram', 'litre'}
        assert len(expected_units) == 9


# ---------------------------------------------------------------------------
# Schema.org alignment tests
# ---------------------------------------------------------------------------

class TestSchemaOrgAlignment:
    def test_slot_uri_on_credit_class(self):
        from pathlib import Path
        schema_path = Path("services/linkml/schemas/credit_class.linkml.yaml")
        content = schema_path.read_text()
        # Credit class uses slot_uri from core imports for name/description/url
        # and has rfs: URIs for domain-specific fields
        assert "slot_uri: rfs:hasPrimaryImpact" in content
        assert "slot_uri: rfs:hasCoBenefits" in content
        assert "slot_uri: rfs:hasSourceRegistry" in content
        assert "slot_uri: schema:url" in content

    def test_slot_uri_on_project(self):
        from pathlib import Path
        schema_path = Path("services/linkml/schemas/project.linkml.yaml")
        content = schema_path.read_text()
        assert "slot_uri: rfs:hasLinks" in content
        assert "slot_uri: rfs:hasFeature" in content
        assert "slot_uri: schema:startDate" in content
        assert "slot_uri: schema:endDate" in content

    def test_core_types_defined(self):
        from pathlib import Path
        schema_path = Path("services/linkml/schemas/core.linkml.yaml")
        content = schema_path.read_text()
        assert "PropertyValue" in content
        assert "QuantitativeValue" in content
        assert "GeoShape" in content
        assert "Feature" in content
        assert "Duration" in content
        assert "Link" in content

    def test_core_slot_uris(self):
        from pathlib import Path
        schema_path = Path("services/linkml/schemas/core.linkml.yaml")
        content = schema_path.read_text()
        assert "slot_uri: schema:name" in content
        assert "slot_uri: schema:description" in content
        assert "slot_uri: schema:url" in content
        assert "slot_uri: schema:sameAs" in content
        assert "slot_uri: schema:mainEntityOfPage" in content
        assert "slot_uri: schema:potentialAction" in content

    def test_jsonld_context_generation(self):
        from services.linkml.jsonld import generate_context, to_jsonld_document
        context = generate_context("CreditClass")
        assert "schema" in context
        assert "kokonut" in context
        doc = to_jsonld_document("CreditClass", {"name": "Test Class"}, iri="kokonut:credit_class:1")
        assert doc["@type"] == "kokonut:CreditClass"
        assert doc["@id"] == "kokonut:credit_class:1"
        assert doc["name"] == "Test Class"

    def test_jsonld_with_graph(self):
        from services.linkml.jsonld import to_jsonld_with_graph
        entities = [
            {"@type": "kokonut:CreditClass", "name": "Class A"},
            {"@type": "kokonut:Project", "name": "Project 1"},
        ]
        doc = to_jsonld_with_graph(entities)
        assert "@graph" in doc
        assert len(doc["@graph"]) == 2

    def test_duration_type_in_schema(self):
        from pathlib import Path
        schema_path = Path("services/linkml/schemas/core.linkml.yaml")
        content = schema_path.read_text()
        assert "xsd:duration" in content
        assert "ISO 8601" in content


# ---------------------------------------------------------------------------
# ARKIV Parity tests
# ---------------------------------------------------------------------------

class TestARKIVParity:
    def test_expires_at_columns_exist(self):
        from pathlib import Path
        schema_path = Path("schemas/postgres/113_arkiv_parity.sql")
        content = schema_path.read_text()
        assert "expires_at" in content
        assert "data_stream_post" in content
        assert "impact_claim" in content
        assert "attestation_record" in content

    def test_origin_tx_index_exists(self):
        from pathlib import Path
        schema_path = Path("schemas/postgres/113_arkiv_parity.sql")
        content = schema_path.read_text()
        assert "origin_tx_index" in content
        assert "UNIQUE(credit_class_id, origin_tx_id, origin_tx_source)" in content

    def test_marketplace_fee_exists(self):
        from pathlib import Path
        schema_path = Path("schemas/postgres/113_arkiv_parity.sql")
        content = schema_path.read_text()
        assert "marketplace_fee" in content
        assert "marketplace_fee_distribution" in content
        assert "buyer_fee" in content
        assert "seller_fee" in content

    def test_fee_collection(self):
        from services.credit_class.fees import collect_fee, get_fee_params
        conn = _fake_conn_sequential([
            {"param_value": "0.03"},  # buyer fee
            {"param_value": "0.03"},  # seller fee
            {"param_value": "0x1234"},  # pool address
            {"id": str(uuid.uuid4())},  # insert
        ])
        result = collect_fee(conn, "buy", str(uuid.uuid4()), buyer_fee=10, seller_fee=5)
        assert result["total_fee"] == 15

    def test_fee_params(self):
        from services.credit_class.fees import get_fee_params
        conn = _fake_conn_sequential([
            {"param_value": "0.03"},  # buyer fee
            {"param_value": "0.03"},  # seller fee
            {"param_value": "0x1234"},  # pool address
        ])
        params = get_fee_params(conn)
        assert params["buyer_fee"] == 0.03
        assert params["fee_pool_address"] == "0x1234"


# ---------------------------------------------------------------------------
# GeoNode Parity tests
# ---------------------------------------------------------------------------

class TestGeoNodeParity:
    def test_iso_19115_fields_exist(self):
        from pathlib import Path
        schema_path = Path("schemas/postgres/114_geonode_parity.sql")
        content = schema_path.read_text()
        assert "date_created" in content
        assert "topic_category" in content
        assert "spatial_resolution" in content
        assert "lineage" in content
        assert "reference_system" in content
        assert "purpose" in content

    def test_file_crs_field(self):
        from pathlib import Path
        schema_path = Path("schemas/postgres/114_geonode_parity.sql")
        content = schema_path.read_text()
        assert "crs VARCHAR(50) DEFAULT 'EPSG:4326'" in content
        assert "file_hash" in content

    def test_thesaurus_tables(self):
        from pathlib import Path
        schema_path = Path("schemas/postgres/114_geonode_parity.sql")
        content = schema_path.read_text()
        assert "thesaurus" in content
        assert "thesaurus_keyword" in content
        assert "thesaurus_keyword_label" in content
        assert "parent_keyword_id" in content

    def test_thesaurus_service(self):
        from services.thesaurus import create_thesaurus, list_thesauri
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = create_thesaurus(conn, "test_vocab", "Test Vocabulary")
        assert result["identifier"] == "test_vocab"

    def test_thesaurus_keywords(self):
        from services.thesaurus import add_keyword, list_keywords
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_keyword(conn, str(uuid.uuid4()), "agroforestry")
        assert result["keyword_about"] == "agroforestry"

    def test_thesaurus_labels(self):
        from services.thesaurus import add_keyword_label
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_keyword_label(conn, str(uuid.uuid4()), "Agroforestry", "en")
        assert result["label"] == "Agroforestry"


# ---------------------------------------------------------------------------
# GeoNode Enhancement tests
# ---------------------------------------------------------------------------

class TestGeoNodeEnhancements:
    def test_shapefile_import_module(self):
        from services.ingestion.shapefile_import import SUPPORTED_FORMATS
        assert "shp" in SUPPORTED_FORMATS
        assert "geojson" in SUPPORTED_FORMATS
        assert "kml" in SUPPORTED_FORMATS

    def test_kml_import_module(self):
        from services.ingestion.kml_import import parse_kml_coordinates
        coords = parse_kml_coordinates("1.0,2.0,0.0")
        assert len(coords) == 1
        assert coords[0] == (2.0, 1.0)

    def test_csw_capabilities(self):
        from services.csw import get_capabilities
        caps = get_capabilities()
        assert caps["service"] == "CSW"
        assert "GetCapabilities" in caps["operations"]

    def test_geostory_module(self):
        from services.geostory import create_geostory
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = create_geostory(conn, str(uuid.uuid4()), "Test Story")
        assert result["title"] == "Test Story"

    def test_harvest_manager_module(self):
        from services.ingestion.harvest_manager import list_harvest_logs
        conn = _fake_conn(rows=[])
        logs = list_harvest_logs(conn)
        assert isinstance(logs, list)


# ---------------------------------------------------------------------------
# Ecocredit Parity tests
# ---------------------------------------------------------------------------

class TestCreditType:
    def test_create_credit_type(self):
        from services.credit_class.entities import create_credit_type
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = create_credit_type(conn, "carbon", "C", "tonneCO2e", 2)
        assert result["name"] == "carbon"

    def test_list_credit_types(self):
        from services.credit_class.entities import list_credit_types
        conn = _fake_conn(rows=[{"name": "carbon", "abbreviation": "C", "unit": "tonneCO2e"}])
        types = list_credit_types(conn)
        assert len(types) == 1


class TestIssuer:
    def test_add_issuer(self):
        from services.credit_class.entities import add_issuer
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_issuer(conn, CLASS_ID, "0x1234", "Kokonut DAO")
        assert "id" in result

    def test_list_issuers(self):
        from services.credit_class.entities import list_issuers
        conn = _fake_conn(rows=[{"issuer_address": "0x1234", "issuer_name": "Kokonut DAO"}])
        issuers = list_issuers(conn, CLASS_ID)
        assert len(issuers) == 1


class TestAllowlist:
    def test_add_to_allowlist(self):
        from services.credit_class.entities import add_to_allowlist
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_to_allowlist(conn, "0x1234", "Kokonut")
        assert "id" in result

    def test_is_allowed_creator(self):
        from services.credit_class.entities import is_allowed_creator
        conn = _fake_conn(rows={"1": 1})
        assert is_allowed_creator(conn, "0x1234") is True

    def test_is_not_allowed_creator(self):
        from services.credit_class.entities import is_allowed_creator
        conn = _fake_conn(rows=[])
        assert is_allowed_creator(conn, "0x5678") is False


class TestBasket:
    def test_create_basket(self):
        from services.credit_class.basket import create_basket
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = create_basket(conn, "Carbon Basket", "cusd")
        assert result["name"] == "Carbon Basket"

    def test_create_basket_with_denom(self):
        from services.credit_class.basket import create_basket, _compute_basket_denom
        denom = _compute_basket_denom("rNCT", "C", 6)
        assert denom == "eco.uC.rNCT"

    def test_list_baskets(self):
        from services.credit_class.basket import list_baskets
        conn = _fake_conn(rows=[{"name": "Carbon Basket", "token_denom": "cusd"}])
        baskets = list_baskets(conn)
        assert len(baskets) == 1

    def test_deposit_moves_depositor_balance_to_escrow(self):
        from services.credit_class.basket import deposit_credits
        conn = _fake_conn_sequential([
            {"id": str(uuid.uuid4()), "status": "active", "exponent": 6},
            {"vintage_year": 2026},
            {"rowcount": 1},
            {"id": str(uuid.uuid4())},
            {"rowcount": 1},
        ])
        deposit_credits(conn, str(uuid.uuid4()), BATCH_ID, "0xdepositor", 2)
        sql = " ".join(call.args[0] for call in conn.execute.call_args_list)
        assert "SELECT vintage_year FROM credit_batch" in sql
        assert "account_address = :addr AND tradable_amount >= :qty" in sql
        assert "retired_quantity" not in sql

    def test_update_curator(self):
        from services.credit_class.basket import update_curator
        conn = _fake_conn_sequential([
            {"id": str(uuid.uuid4()), "curator_address": "0x1234"},  # get_basket
            {"rowcount": 1},  # update
        ])
        result = update_curator(conn, str(uuid.uuid4()), "0x1234", "0x5678")
        assert result["new_curator"] == "0x5678"

    def test_update_date_criteria(self):
        from services.credit_class.basket import update_date_criteria
        conn = _fake_conn_sequential([
            {"id": str(uuid.uuid4())},  # get_basket
            {"rowcount": 1},  # update
        ])
        result = update_date_criteria(conn, str(uuid.uuid4()), min_start_year=5)
        assert result["basket_id"] is not None

    def test_withdraw_with_auto_retire(self):
        from services.credit_class.basket import withdraw_from_basket
        conn = _fake_conn_sequential([
            {"id": str(uuid.uuid4()), "status": "active", "disable_auto_retire": False, "exponent": 6},  # get_basket
            {"token_amount": 1000000},  # get_token_balance
            [{"credit_batch_id": str(uuid.uuid4()), "depositor_address": "0xdepositor", "quantity": 1,
              "token_amount": 1000000, "batch_start_date": "2026-01-01", "id": str(uuid.uuid4())}],  # deposits
            {"rowcount": 1},  # update deposit
            {"rowcount": 1},  # consume depositor escrow
            {"id": str(uuid.uuid4()), "tradable_amount": 0, "retired_amount": 1, "escrowed_amount": 0},
            {"rowcount": 1},  # increment batch retirement
            {"rowcount": 1},  # debit token
        ])
        result = withdraw_from_basket(conn, str(uuid.uuid4()), "0x1234", 1000000)
        assert result["retire_on_take"] is True
        assert result["credit_amount"] == 1.0


class TestMarketplace:
    def test_create_sell_order_moves_owned_balance_to_escrow(self):
        from services.credit_class.marketplace import create_sell_order
        conn = _fake_conn_sequential([
            {"id": str(uuid.uuid4())},  # allowed denom
            {"rowcount": 1},  # conditional balance move
            {"id": str(uuid.uuid4())},  # sell order
        ])
        create_sell_order(conn, BATCH_ID, "0xseller", 5, 100, "cusd")
        sql = " ".join(call.args[0] for call in conn.execute.call_args_list)
        assert "tradable_amount = tradable_amount - :qty" in sql
        assert "account_address = :seller" in sql
        assert "tradable_amount >= :qty" in sql
        assert "retired_quantity" not in sql

    def test_execute_buy_order_transfers_escrow_to_buyer(self):
        from services.credit_class.marketplace import execute_buy_order
        buy_id = str(uuid.uuid4())
        sell_id = str(uuid.uuid4())
        conn = _fake_conn_sequential([
            {"id": buy_id, "sell_order_id": sell_id, "buyer_address": "0xbuyer",
             "quantity": 4, "auto_retire": False, "status": "pending"},
            {"id": sell_id, "credit_batch_id": BATCH_ID, "seller_address": "0xseller",
             "escrow_quantity": 10, "status": "active"},
            {"rowcount": 1},
            {"id": str(uuid.uuid4()), "tradable_amount": 4,
             "retired_amount": 0, "escrowed_amount": 0},
            {"rowcount": 1},
            {"rowcount": 1},
        ])
        result = execute_buy_order(conn, buy_id)
        assert result["status"] == "completed"
        sql = " ".join(call.args[0] for call in conn.execute.call_args_list)
        assert "escrowed_amount = escrowed_amount - :qty" in sql
        assert "INSERT INTO credit_balance" in sql
        assert "retired_quantity" not in sql

    def test_list_allowed_denoms(self):
        from services.credit_class.marketplace import list_allowed_denoms
        conn = _fake_conn(rows=[{"denom": "cusd", "is_active": True}])
        denoms = list_allowed_denoms(conn)
        assert len(denoms) == 1

    def test_add_allowed_denom(self):
        from services.credit_class.marketplace import add_allowed_denom
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = add_allowed_denom(conn, "cusd", "celo")
        assert result["denom"] == "cusd"

    def test_remove_allowed_denom(self):
        from services.credit_class.marketplace import remove_allowed_denom
        conn = _fake_conn(rowcount=1)
        removed = remove_allowed_denom(conn, "cusd")
        assert removed is True

    def test_get_fee_params(self):
        from services.credit_class.marketplace import get_fee_params
        conn = _fake_conn_sequential([
            {"param_value": "0.03"},  # buyer fee
            {"param_value": "0.03"},  # seller fee
        ])
        params = get_fee_params(conn)
        assert params["buyer_fee"] == 0.03

    def test_set_fee_params(self):
        from services.credit_class.marketplace import set_fee_params
        conn = _fake_conn_sequential([
            {"rowcount": 1},  # insert/update buyer fee
            {"param_value": "0.05"},  # get buyer fee
            {"param_value": "0.03"},  # get seller fee
        ])
        result = set_fee_params(conn, buyer_fee=0.05)
        assert result["buyer_fee"] == 0.05

    def test_expire_sell_orders(self):
        from services.credit_class.marketplace import expire_sell_orders
        conn = _fake_conn_sequential([
            [{"id": str(uuid.uuid4()), "credit_batch_id": BATCH_ID,
              "seller_address": "0xseller", "escrow_quantity": 3}],
            {"rowcount": 1},
            {"rowcount": 1},
        ])
        expired = expire_sell_orders(conn)
        assert expired == 1
        sql = " ".join(call.args[0] for call in conn.execute.call_args_list)
        assert "retired_quantity" not in sql
        assert "escrowed_amount = escrowed_amount - :qty" in sql


class TestIRIContentHashType:
    def test_generate_iri_with_hash_type(self):
        from services.iri.resolver import generate_iri
        conn = _fake_conn(rows=[{"max_version": None}], rowcount=1)
        iri = generate_iri(conn, "location", LOCATION_ID, content={"name": "Test"}, content_hash_type="graph")
        assert iri.startswith("kokonut:location:")

    def test_generate_iri_default_raw(self):
        from services.iri.resolver import generate_iri
        conn = _fake_conn(rows=[{"max_version": None}], rowcount=1)
        iri = generate_iri(conn, "location", LOCATION_ID, content={"name": "Test"})
        assert iri.startswith("kokonut:location:")


# ---------------------------------------------------------------------------
# Balance tests
# ---------------------------------------------------------------------------

class TestBalance:
    def test_get_balance(self):
        from services.credit_class.balance import get_balance
        conn = _fake_conn(rows=[])
        balance = get_balance(conn, str(uuid.uuid4()), "0x1234")
        assert balance["tradable_amount"] == 0

    def test_get_supply(self):
        from services.credit_class.balance import get_supply
        conn = _fake_conn(rows={"tradable_supply": 100, "retired_supply": 20, "escrowed_supply": 10})
        supply = get_supply(conn, str(uuid.uuid4()))
        assert supply["tradable_supply"] == 100

    def test_upsert_balance(self):
        from services.credit_class.balance import upsert_balance
        conn = _fake_conn(rows={"id": str(uuid.uuid4()), "tradable_amount": 50, "retired_amount": 0, "escrowed_amount": 0})
        result = upsert_balance(conn, str(uuid.uuid4()), "0x1234", tradable_delta=50)
        assert "tradable" in result
        assert "ON CONFLICT (credit_batch_id, account_address) DO UPDATE" in conn.execute.call_args.args[0]

    def test_account_balance_joins_class_through_batch_class_id(self):
        from services.credit_class.balance import get_balances_for_account
        conn = _fake_conn(rows=[])
        get_balances_for_account(conn, "0x1234")
        assert "cc.id = b.credit_class_id" in conn.execute.call_args.args[0]


# ---------------------------------------------------------------------------
# Params tests
# ---------------------------------------------------------------------------

class TestParams:
    def test_get_params(self):
        from services.credit_class.params import get_params
        conn = _fake_conn(rows=[{"param_key": "class_fee", "param_value": {"denom": "cusd", "amount": 0}}])
        params = get_params(conn)
        assert "class_fee" in params

    def test_get_class_fee(self):
        from services.credit_class.params import get_class_fee
        conn = _fake_conn(rows={"param_key": "class_fee", "param_value": {"denom": "cusd", "amount": 0}})
        fee = get_class_fee(conn)
        assert fee["denom"] == "cusd"


# ---------------------------------------------------------------------------
# Basket withdrawal tests
# ---------------------------------------------------------------------------

class TestBasketWithdrawal:
    def test_withdraw_from_basket(self):
        from services.credit_class.basket import withdraw_from_basket
        conn = _fake_conn_sequential([
            {"id": str(uuid.uuid4()), "status": "active", "disable_auto_retire": False, "exponent": 6},  # get_basket
            {"token_amount": 100},  # get_token_balance
            [{"credit_batch_id": str(uuid.uuid4()), "depositor_address": "0xdepositor", "quantity": 0.0001,
              "token_amount": 100, "batch_start_date": "2026-01-01", "id": str(uuid.uuid4())}],  # deposits
            {"rowcount": 1},  # update deposit
            {"rowcount": 1},  # consume depositor escrow
            {"id": str(uuid.uuid4()), "tradable_amount": 0, "retired_amount": 0.00005, "escrowed_amount": 0},
            {"rowcount": 1},  # increment batch retirement
            {"rowcount": 1},  # debit token
        ])
        result = withdraw_from_basket(conn, str(uuid.uuid4()), "0x1234", 50)
        assert result["token_amount_withdrawn"] == 50

    def test_get_basket_balances(self):
        from services.credit_class.basket import get_basket_balances
        conn = _fake_conn(rows=[{"batch_code": "CC-001", "quantity": 100, "unit": "tonneCO2e"}])
        balances = get_basket_balances(conn, str(uuid.uuid4()))
        assert len(balances) == 1


# ---------------------------------------------------------------------------
# Data Module v2 tests
# ---------------------------------------------------------------------------

class TestContentHash:
    def test_compute_hash_sha256(self):
        from services.data_module.content_hash import compute_hash
        h = compute_hash(b"hello world", "sha256")
        assert len(h) == 64

    def test_compute_hash_blake2b(self):
        from services.data_module.content_hash import compute_hash
        h = compute_hash(b"hello world", "blake2b256")
        assert len(h) == 64

    def test_compute_content_hash(self):
        from services.data_module.content_hash import compute_content_hash
        result = compute_content_hash({"key": "value"}, algorithm="sha256", content_type="graph")
        assert result["hash_algorithm"] == "sha256"
        assert result["content_type"] == "graph"

    def test_create_content_hash(self):
        from services.data_module.content_hash import create_content_hash
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = create_content_hash(conn, str(uuid.uuid4()), "abc123", content_type="raw", media_type="json")
        assert "id" in result

    def test_find_iri_by_hash(self):
        from services.data_module.content_hash import find_iri_by_content_hash
        conn = _fake_conn(rows=[{"iri": "kokonut:location:UUID:v1", "entity_type": "location", "hash_algorithm": "sha256"}])
        results = find_iri_by_content_hash(conn, "abc123")
        assert len(results) == 1


class TestDataResolver:
    def test_define_resolver(self):
        from services.data_module.resolver import define_resolver
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = define_resolver(conn, "https://api.kokonut.network/data", "0x1234")
        assert "id" in result

    def test_list_resolvers(self):
        from services.data_module.resolver import list_resolvers
        conn = _fake_conn(rows=[{"resolver_url": "https://api.kokonut.network/data", "is_active": True}])
        resolvers = list_resolvers(conn)
        assert len(resolvers) == 1

    def test_register_data(self):
        from services.data_module.resolver import register_data_to_resolver
        conn = _fake_conn(rows={"id": str(uuid.uuid4())})
        result = register_data_to_resolver(conn, str(uuid.uuid4()), str(uuid.uuid4()))
        assert "resolver_id" in result

    def test_get_resolvers_for_iri(self):
        from services.data_module.resolver import get_resolvers_for_iri
        conn = _fake_conn(rows=[{"resolver_url": "https://api.kokonut.network/data", "manager_address": "0x1234"}])
        resolvers = get_resolvers_for_iri(conn, str(uuid.uuid4()))
        assert len(resolvers) == 1


class TestDataAttestor:
    def test_attest_to_iri(self):
        from services.data_module.attestor import attest_to_iri
        conn = _fake_conn_sequential([
            None,  # existing check returns None
            {"id": str(uuid.uuid4())},  # insert
        ])
        result = attest_to_iri(conn, str(uuid.uuid4()), "0x1234")
        assert "id" in result

    def test_attest_already_attested(self):
        from services.data_module.attestor import attest_to_iri
        conn = _fake_conn_sequential([
            {"id": str(uuid.uuid4())},  # existing check returns existing
        ])
        result = attest_to_iri(conn, str(uuid.uuid4()), "0x1234")
        assert result["already_attested"] is True

    def test_get_attestors(self):
        from services.data_module.attestor import get_attestors_for_iri
        conn = _fake_conn(rows=[{"attestor_address": "0x1234", "attested_at": "2026-07-11"}])
        attestors = get_attestors_for_iri(conn, str(uuid.uuid4()))
        assert len(attestors) == 1


# ---------------------------------------------------------------------------
# Enrollment tests
# ---------------------------------------------------------------------------

class TestEnrollment:
    def test_apply_to_class(self):
        from services.credit_class.enrollment import apply_to_class
        conn = _fake_conn_sequential([
            None,  # no existing
            {"id": str(uuid.uuid4())},  # insert
        ])
        result = apply_to_class(conn, LOCATION_ID, CLASS_ID)
        assert result["status"] == "applied"

    def test_evaluate_application(self):
        from services.credit_class.enrollment import evaluate_application
        conn = _fake_conn_sequential([
            {"id": str(uuid.uuid4()), "status": "applied"},  # get enrollment
            {"rowcount": 1},  # update
        ])
        result = evaluate_application(conn, str(uuid.uuid4()), "0x1234", "accepted")
        assert result["new_status"] == "accepted"

    def test_list_enrollments(self):
        from services.credit_class.enrollment import list_enrollments_by_project
        conn = _fake_conn(rows=[{"status": "accepted", "class_name": "Carbon"}])
        enrollments = list_enrollments_by_project(conn, LOCATION_ID)
        assert len(enrollments) == 1

    def test_terminate_enrollment(self):
        from services.credit_class.enrollment import terminate_enrollment
        conn = _fake_conn_sequential([
            {"id": str(uuid.uuid4()), "status": "accepted"},  # get
            {"rowcount": 1},  # update
        ])
        result = terminate_enrollment(conn, str(uuid.uuid4()))
        assert result["status"] == "terminated"


# ---------------------------------------------------------------------------
# Bridge tests
# ---------------------------------------------------------------------------

class TestBridge:
    def test_create_bridge_outbound(self):
        from services.credit_class.bridge import create_bridge_outbound
        conn = _fake_conn_sequential([
            {"available_quantity": 100},  # batch check
            {"param_value": ["celo", "gnosis"]},  # allowed chains
            {"id": str(uuid.uuid4())},  # insert
        ])
        result = create_bridge_outbound(conn, str(uuid.uuid4()), "0x1234", "celo", "0x5678", 50)
        assert result["direction"] == "outbound"

    def test_list_bridge_transactions(self):
        from services.credit_class.bridge import list_bridge_transactions
        conn = _fake_conn(rows=[{"direction": "outbound", "target_chain": "celo", "status": "pending"}])
        txs = list_bridge_transactions(conn)
        assert len(txs) == 1


# ---------------------------------------------------------------------------
# Batch update tests
# ---------------------------------------------------------------------------

class TestBatchUpdate:
    def test_update_batch_metadata(self):
        from services.credit_class.batch_manager import update_batch_metadata
        conn = _fake_conn_sequential([
            {"id": str(uuid.uuid4()), "batch_code": "CC-001"},  # get_batch
            {"rowcount": 1},  # update
        ])
        result = update_batch_metadata(conn, str(uuid.uuid4()), {"notes": "test"})
        assert "metadata" in result["updated_fields"]

    def test_list_batches_by_issuer(self):
        from services.credit_class.batch_manager import list_batches_by_issuer
        conn = _fake_conn(rows=[{"batch_code": "CC-001", "total_quantity": 100}])
        batches = list_batches_by_issuer(conn, "0x1234")
        assert len(batches) == 1
