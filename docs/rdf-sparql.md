# RDF And SPARQL

Kokonut Intelligence provides a native RDF-style triple store for semantic queries, provenance, linked-data exports, and cross-system interoperability. PostgreSQL and Directus remain the canonical record layer; RDF is a derived projection and does not replace governed source records or their lifecycle controls.

## Architecture

```text
Governed Records
      |
      v
Graph Builder / Evidence Chain
      |
      v
RDF Triples + Named Graph Registry
      |
      +--> Triple CLI
      +--> Basic SPARQL-to-SQL Queries
      +--> Turtle / N-Triples / JSON-LD
      +--> Metadata Graph API
```

## Namespaces And Named Graphs

Migration `104_rdf_triples.sql` seeds these namespace prefixes:

| Prefix | Namespace |
|---|---|
| `schema` | `http://schema.org/` |
| `regen` | `https://schema.regen.network#` |
| `cids` | `https://ontology.commonapproach.org/cids#` |
| `kokonut` | `https://kokonut.network/ontology#` |
| `geojson` | `https://purl.org/geojson/vocab#` |
| `qudt` | `https://qudt.org/schema/qudt/` |
| `sdgs` | `https://metadata.un.org/sdgs/` |

Named graphs are tracked in `rdf_named_graph` with a name, description, source system, triple count, and last-build timestamp. Common graph names include:

- `location:<location_uuid>` for a persisted location projection;
- `evidence:<claim_uuid>` for an impact-claim evidence chain;
- `credit:<credit_uuid>` and `claim:<claim_uuid>` during graph construction before aggregation into a location graph.

## Triple Store

The `rdf_triple` table stores one RDF statement per row:

| Field | Purpose |
|---|---|
| `subject` | Subject IRI or compact Kokonut identifier |
| `predicate` | Predicate IRI |
| `object_value` | Literal object value; mutually exclusive with `object_iri` |
| `object_type` | Literal type such as `string`, `integer`, `decimal`, or `boolean` |
| `object_iri` | IRI object; mutually exclusive with `object_value` |
| `graph_name` | Named graph containing the statement |
| `source_table` | Canonical source table, when known |
| `source_id` | Canonical source record, when known |
| `source_column` | Source column, when known |
| `content_hash` | Hash of the triple terms for provenance/integrity |
| `created_at` | Triple creation time |

The store has indexes for subject, predicate, object IRI, graph, and source record. The graph-integrity migration removes duplicate rows, enforces exactly one object representation, and creates separate NULL-safe uniqueness indexes for literal and IRI objects.

## Graph Builder Scope

`services/rdf/graph_builder.py` currently projects a focused set of governed records:

- `location` name, description, and coordinates;
- verified or published `farm_registry_record` name and project summary;
- `carbon_credit` code, vintage, methodology, issuable quantity, retired quantity, and location;
- `impact_claim` type, text, value, location, and evidence CID link.

The builder does not automatically materialize every governed table in the platform. `build_full_graph()` collects location, credit, and claim triples for one location. `persist_graph()` deletes and rebuilds the aggregate `location:<UUID>` graph, then updates its named-graph count and build timestamp.

```python
from services.rdf.graph_builder import build_full_graph, persist_graph

triples = build_full_graph(conn, location_id)
count = persist_graph(conn, location_id)
```

The returned triples include subject, predicate, literal or IRI object, graph name, and source provenance fields where available.

## Evidence Chains

`services/rdf/evidence_chain.py` builds a separate `evidence:<claim_uuid>` graph for an `impact_claim`. It can link:

- the claim to an evidence CID;
- evidence to a content hash;
- the claim to an attestation UID;
- the claim to an external verifier;
- the claim to its location;
- the claim to a stakeholder outcome.

`verify_evidence_chain()` checks for evidence and location links and reports whether the chain is structurally valid. This helper is not an evidence-maturity or publication gate. It does not independently verify the evidence content, attestation, external verifier, or claim lifecycle.

## CLI Commands

The RDF CLI uses the shared database connection and keeps PostgreSQL access inside the service runtime:

```bash
# Build and persist the location graph
python3 -m services.rdf.cli build --location-id UUID

# Query by optional subject, predicate, or graph
python3 -m services.rdf.cli query --subject "kokonut:location:UUID"
python3 -m services.rdf.cli query --predicate "http://schema.org/name" --graph "location:UUID"

# Serialize one required named graph
python3 -m services.rdf.cli serialize --format turtle --graph "location:UUID"
python3 -m services.rdf.cli serialize --format ntriples --graph "location:UUID"
python3 -m services.rdf.cli serialize --format jsonld --graph "location:UUID"

# Count triples, optionally within a graph
python3 -m services.rdf.cli count --graph "location:UUID"

# List graph names, counts, and build timestamps
python3 -m services.rdf.cli list-graphs
```

`query` supports subject, predicate, object IRI, and graph filtering in the underlying store, but the current CLI exposes only subject, predicate, and graph filters. Store queries default to a limit of 1,000 rows.

## Supported SPARQL Subset

The SPARQL engine is intentionally a strict basic-graph-pattern translator, not a general SPARQL implementation. Supported form:

```sparql
SELECT ?s ?p ?o
WHERE {
  ?s <http://schema.org/name> ?o .
}
LIMIT 10
```

Supported terms are variables, `<IRI>` terms, and quoted string literals. Multiple triple patterns are translated into a SQL cross join with equality constraints for repeated variables.

```python
from services.rdf.sparql_engine import execute_sparql

result = execute_sparql(conn, """
    SELECT ?s ?p ?o
    WHERE {
        ?s <http://schema.org/name> ?o .
    }
    LIMIT 10
""")
# {"variables": ["s", "p", "o"], "results": [...]}
```

The parser rejects or does not implement:

- `ASK`, `CONSTRUCT`, and `DESCRIBE`;
- `FILTER`, `OPTIONAL`, `UNION`, and `GRAPH` clauses;
- aggregates, ordering, grouping, and namespace declarations;
- literal subjects or predicates;
- unbound selected variables;
- duplicate selected variables;
- malformed triple patterns.

Safety and resource limits are enforced:

- maximum query length: 10,000 characters;
- default result limit: 1,000;
- maximum result limit: 1,000;
- requested limits below 1 are rejected;
- SQL terms are parameterized rather than interpolated from the query.

The engine returns variable names and mapped result rows. It does not provide a general-purpose RDF reasoner, inference engine, ontology validator, or authorization layer.

## Serialization

The serializer module supports Turtle, N-Triples, JSON-LD, and a basic JSON-LD-to-triple conversion:

```python
from services.rdf.serializers import from_jsonld, to_jsonld, to_ntriples, to_turtle

turtle = to_turtle(triples, namespaces={"schema": "http://schema.org/"})
ntriples = to_ntriples(triples)
jsonld = to_jsonld(triples, context={"schema": "http://schema.org/"})
triples_again = from_jsonld(jsonld, graph_name="default")
```

Serialization behavior:

- Turtle can emit caller-supplied `@prefix` declarations and datatype markers for integer, decimal, and boolean literals.
- N-Triples emits one statement per line and escapes backslashes and quotes in literal values.
- JSON-LD returns an `@graph` array and derives property names from the final path or fragment segment of each predicate.
- JSON-LD IRI objects become `{"@id": ...}` values; literal values are converted back to basic Python types when their object type is known.
- `from_jsonld()` skips `@id`, `@type`, and `@context`, and represents other values as literal or IRI triples.
- The CLI does not automatically load prefix declarations from `rdf_namespace`; pass namespaces to the Python Turtle serializer when required.

## Metadata Graph API

The separately launched FastAPI metadata service exposes RDF-related endpoints:

```text
POST /data/v2/sparql
GET  /data/v2/graphs
GET  /data/v2/metadata-graph/{iri}
GET  /data/v2/entity/{entity_type}/{entity_id}
```

The SPARQL endpoint accepts a query parameter and returns the same `variables`/`results` shape as `execute_sparql()`. The graph endpoint lists named graph metadata. Metadata and entity endpoints resolve governed metadata and return `404` when the IRI or entity is not found.

This API is separate from the default gateway. It is not automatically routed through Caddy or exposed as a Compose service unless deployment configuration adds it. Protect it with the deployment’s authentication, TLS, network, and rate-limit controls before external exposure.

## Governance And Provenance Boundaries

- RDF triples are derived projections and can become stale until the relevant graph is rebuilt.
- A triple’s source table and source ID provide lineage, not proof that the source record is public or verified.
- Public or partner exports must apply the source record’s lifecycle, consent, evidence, registry, and privacy gates before serialization.
- Do not treat a graph query result as permission to expose raw private stakeholder evidence.
- Do not infer credit issuance, external registry recognition, or claim verification solely from a linked RDF edge.
- JSON-LD and Turtle output are compatibility formats; PostgreSQL/Directus remains canonical.

## References And Verification

- RDF schema: `schemas/postgres/104_rdf_triples.sql`
- Integrity repair migration: `schemas/postgres/171_graph_integrity_repairs.sql`
- Graph builder: `services/rdf/graph_builder.py`
- Triple store: `services/rdf/triple_store.py`
- SPARQL parser/translator: `services/rdf/sparql_engine.py`
- Serializers: `services/rdf/serializers.py`
- Evidence chains: `services/rdf/evidence_chain.py`
- RDF CLI: `services/rdf/cli.py`
- Metadata API: `services/metadata_api/app.py`
- Linked-data tests: `tests/test_linked_data.py`

Run the linked-data tests with:

```bash
python3 -m pytest tests/test_linked_data.py -v
```
