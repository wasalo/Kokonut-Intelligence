# rdf

`services.rdf` — RDF Triple Store: Subject-predicate-object graph for semantic queries.

## CLI Usage

```bash
python3 -m services.rdf.cli --help
```

## Modules

- `cli` — RDF CLI: build, query, serialize.
- `evidence_chain` — Evidence chaining via RDF: provenance chains for impact claims.
- `graph_builder` — RDF graph builder: auto-generate triples from governed records.
- `serializers` — RDF serialization: Turtle, N-Triples, JSON-LD.
- `sparql_engine` — SPARQL-to-SQL translator for basic graph pattern queries.
- `triple_store` — RDF triple store: CRUD and query operations.

## Files

6 Python modules
