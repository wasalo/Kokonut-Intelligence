# RDF & SPARQL

## Overview

Kokonut Intelligence includes a native RDF triple store with SPARQL query support for semantic data operations.

## Architecture

```
Governed Records → Graph Builder → RDF Triples → Triple Store
                                                       ↓
                                              SPARQL Queries
                                                       ↓
                                              JSON-LD Export
```

## Triple Store

Triples are stored in the `rdf_triple` table with subject-predicate-object structure:

```sql
CREATE TABLE rdf_triple (
    id UUID PRIMARY KEY,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_value TEXT,
    object_type VARCHAR(50),
    object_iri TEXT,
    graph_name VARCHAR(100) NOT NULL,
    source_table VARCHAR(100),
    source_id UUID
);
```

## CLI Commands

```bash
# Build RDF graph for a location
python3 -m services.rdf.cli build --location-id UUID

# Query triples
python3 -m services.rdf.cli query --subject "kokonut:location:UUID"

# Serialize to Turtle
python3 -m services.rdf.cli serialize --format turtle --graph "location:adelphi"

# Count triples
python3 -m services.rdf.cli count --graph "location:adelphi"

# List named graphs
python3 -m services.rdf.cli list-graphs
```

## Graph Builder

The graph builder (`services/rdf/graph_builder.py`) automatically generates RDF triples from governed records:

```python
from services.rdf.graph_builder import build_full_graph

# Build complete graph for a location
triples = build_full_graph(conn, location_id)
# Returns list of {subject, predicate, object_value/object_iri, graph_name}
```

## SPARQL Queries

SPARQL queries are translated to SQL against the `rdf_triple` table:

```python
from services.rdf.sparql_engine import execute_sparql

results = execute_sparql(conn, """
    SELECT ?s ?p ?o
    WHERE {
        ?s <http://schema.org/name> ?o .
    }
    LIMIT 10
""")
```

## Serialization

```python
from services.rdf.serializers import to_turtle, to_ntriples, to_jsonld

# Turtle format
turtle = to_turtle(triples, namespaces={"schema": "http://schema.org/"})

# N-Triples format
nt = to_ntriples(triples)

# JSON-LD format
jsonld = to_jsonld(triples, context={"schema": "http://schema.org/"})
```
