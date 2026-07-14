# Evidence Lineage Graph

The evidence-lineage graph is a derived PostgreSQL read model. PostgreSQL and Directus canonical records remain authoritative, while RDF remains the interoperability and JSON-LD export layer.

## Scope

Version 1 projects only explicit or conservatively validated relationships among locations, farm registry records, metric definitions and values, impact claims, evidence CIDs or hashes, and published attestations and schemas.

It deliberately excludes untyped `source_record_ids`, inferred claim-to-metric-value links, report JSON parsing, private evidence bodies, and reviewer UUIDs without explicit foreign keys.

## Generations

A rebuild:

1. Opens a `REPEATABLE READ` transaction.
2. Applies bounded statement and lock timeouts.
3. Acquires a transaction-scoped advisory lock.
4. Builds and validates a complete candidate generation.
5. Verifies persisted node and edge counts.
6. Supersedes the prior generation and switches the active pointer atomically.

Any failure rolls back the candidate and leaves the prior generation active. Consecutive builds over unchanged canonical sources produce the same content hash.

## Governance

Audience is derived from canonical lifecycle, metric verification, claim maturity, Celo attestation validity, active location status, and verified or published farm registry eligibility. Callers cannot assign projection audience.

The public SQL view requires public edges, public endpoints, current temporal validity, an active location, and registry eligibility. General traversal remains private.

## Commands

```bash
python3 -m services.graph_projection rebuild --actor OPERATOR
python3 -m services.graph_projection status
python3 -m services.graph_projection validate
python3 -m services.graph_projection query \
  --entity-key location:UUID \
  --depth 2 \
  --node-cap 100 \
  --audience internal
```

Traversal is limited to depth 5 and 500 nodes, uses an edge-type allowlist, supports location scoping, and reads only the active generation.
