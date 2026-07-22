# Subgraph Indexer Guide

`services.ingestion.subgraph_indexer` is a legacy/experimental adapter for
The Graph-style EAS subgraph endpoints. It is not the canonical EAS or Kokonut
governance indexer.

Current production paths are:

| Source | Implementation | Scope |
|---|---|---|
| EAS Scan GraphQL API | `services/ingestion/eas_indexer.py` | EAS attestations and schemas on configured chains, including Celo |
| Gnosis/Moloch RPC events | `services/ingestion/gnosis_indexer.py` | Legacy Kokonut Moloch v2 history |
| Baal RPC events | `services/ingestion/baal_indexer.py` | Kokonut DAO Moloch v3 governance state |
| The Graph adapter | `services/ingestion/subgraph_indexer.py` | Legacy `eas` and `eas_schema` subgraph queries |

Do not describe this module as a source of current treasury, governance, or
Digital Lego event data. Those integrations are not implemented here.

## Current Scope

The adapter currently configures two endpoints:

```python
SUBGRAPH_ENDPOINTS = {
    "eas": "https://api.studio.thegraph.com/query/eas/attestations/v0.0.1",
    "eas_schema": "https://api.studio.thegraph.com/query/eas/schemas/v0.0.1",
}
```

With no protocol argument, the adapter iterates over those configured keys.
`eas` fetches schema registrations and attestations. `eas_schema` only logs
that schemas are handled by `eas`; it does not perform an independent import.
The CLI accepts `kokonut`, but no endpoint is configured for it, so it only
logs an unknown-protocol warning.

The canonical EAS implementation uses chain-specific EAS Scan endpoints in
`services/ingestion/eas_indexer.py`:

- Optimism: `https://optimism.easscan.org/graphql`
- Base: `https://base.easscan.org/graphql`
- Celo: `https://celo.easscan.org/graphql`

The direct EAS indexer uses timestamp/API pagination and is separate from this
block-oriented legacy adapter. The Celo deployment and pilot schemas remain
the repository's primary EAS context.

## CLI

The only registered flag is `--protocol`:

```bash
python3 -m services.ingestion.subgraph_indexer
python3 -m services.ingestion.subgraph_indexer --protocol eas
python3 -m services.ingestion.subgraph_indexer --protocol eas_schema
```

The following documented flags are not implemented by this module and fail
argument parsing:

- `--dry-run`
- `--from-block`
- `--to-block`

There is no preview mode. Normal execution writes to PostgreSQL, ClickHouse,
`ingestion_log`, and `chain_indexer_status`. Run it only against an intended
database and review the source code's current limitations before use.

## Write Behavior

For `eas`, the adapter attempts to:

1. Fetch at most 100 schema registrations.
2. Insert schemas into `attestation_schema`.
3. Fetch at most 100 attestations.
4. Insert records into `attestation_record`.
5. Write analytical rows to ClickHouse `attestation_events`.
6. Record a batch result in `ingestion_log`.
7. Update the Ethereum/subgraph row in `chain_indexer_status`.

The PostgreSQL and ClickHouse writes are not one atomic transaction. ClickHouse
insert failures are logged as warnings and do not fail the PostgreSQL path.
The outer connection is committed after protocol processing.

The current adapter also has governance and schema limitations:

- Imported attestations are written with `status = 'published'`; indexing is
  not human verification and must not be described as such.
- The importer hardcodes `chain = 'ethereum'`, while the canonical pilot EAS
  deployment is on Celo.
- A schema ID is looked up only from the current schema response; an
  attestation whose schema was not returned in that batch may fail because
  `attestation_record.schema_id` is required.
- The recipient wallet is written to `subject_id`, although the canonical
  column is UUID-oriented.
- The block timestamp is calculated for the import path but is not persisted in
  the PostgreSQL attestation row.
- Schema and attestation inserts use `ON CONFLICT DO NOTHING`; changed source
  metadata is not reconciled.

Until these constraints are addressed and covered by tests, treat this adapter
as legacy ingestion rather than a production-grade canonical indexer.

## Cursor And Idempotency

The adapter queries `chain_indexer_status` for the maximum block associated
with `chain = 'ethereum'`, `indexer_type = 'subgraph'`, and a protocol metadata
filter. It then updates the shared status row with the maximum block observed.

This is not a reliable per-protocol cursor:

- `chain_indexer_status` is unique by `(chain, indexer_type)`, so `eas` and
  `eas_schema` can contend for the same row.
- The status update does not persist the protocol metadata used by the read
  query.
- Only one page of 100 records is requested; there is no pagination loop.
- The cursor can advance past records that were not included in that page.
- Block number alone cannot distinguish multiple events in one block or safely
  handle replay boundaries.
- Attestation deduplication relies primarily on the database's unique
  `attestation_uid` constraint and `ON CONFLICT DO NOTHING`.

Do not reset a cursor by directly editing a shared status row without first
checking target records, preserving evidence, and planning for replay and
duplicate handling. Use the status commands below for inspection before any
operator-led recovery.

## Configuration And Runtime

The hardcoded subgraph URLs above are the active source configuration. The
imported `EAS_GRAPHQL_URL` value is not used by this module, and `GRAPH_API_KEY`
is not defined or sent as an authorization header. Setting it does not resolve
rate limiting for this adapter.

The adapter uses the common database and ClickHouse environment settings. For
Compose worker execution, use service names such as `database` and
`clickhouse`; PostgreSQL and ClickHouse are private in the base Compose setup.
Host commands using `localhost` require an explicit port-publishing override,
such as the CI Compose override.

Operational setup follows the repository workflow:

```bash
source scripts/load-secrets.sh
docker compose up -d
python3 -m services.ingestion.subgraph_indexer --protocol eas
```

For a worker/container deployment, run the command from the configured worker
environment rather than assuming host database ports are available.

## Monitoring

Inspect ingestion records and indexer state with the shared status CLI:

```bash
python3 -m services.ingestion.status log --source subgraph
python3 -m services.ingestion.status log --source subgraph --status failed
python3 -m services.ingestion.status indexers
python3 -m services.ingestion.status summary
```

The adapter writes successful and failed batch records to `ingestion_log` with
source `subgraph`. `chain_indexer_status` is shared state keyed by chain and
indexer type, not a durable independent cursor for each configured protocol.
Inspect both tables before replay or recovery.

## Data Queries

Use the canonical database connection appropriate to the runtime. In a worker
container, the database host is normally `database`; `localhost` is valid only
when PostgreSQL is explicitly published to the host.

For example, inspect recent records without assuming that this legacy adapter
populated every canonical field:

```sql
SELECT ar.attestation_uid,
       ar.status,
       ar.chain,
       ar.subject_type,
       ar.subject_id,
       ar.tx_hash,
       ar.created_at
FROM attestation_record ar
ORDER BY ar.created_at DESC
LIMIT 10;
```

For production EAS data, identify the chain and ingestion path before querying
or interpreting `attestation_record`. Fields such as `claim_type` and
`attested_at` are not reliably populated by this subgraph adapter.

## Adding A Source

Adding a new endpoint is not sufficient to make a source supported. A new
adapter must define and test:

1. A GraphQL query matching the deployed schema, with stable ascending order.
2. Endpoint and chain metadata, without embedding secrets.
3. Real pagination using variables that change between requests.
4. Explicit GraphQL error handling in addition to HTTP error handling.
5. Retry behavior for the actual transient failures, with bounded attempts.
6. Canonical-table-compatible normalization, including UUID fields, chain,
   timestamps, lifecycle status, and required foreign keys.
7. Stable event identity and database deduplication semantics.
8. A cursor design that does not share unrelated protocols' state.
9. PostgreSQL/ClickHouse transaction and partial-failure behavior.
10. Ingestion logging, status updates, replay behavior, and focused tests.

A basic query shape may look like this, but field names and pagination must be
validated against the deployed subgraph:

```graphql
query GetEvents($lastBlock: Int!, $first: Int!, $skip: Int!) {
  protocolEvents(
    first: $first
    skip: $skip
    orderBy: blockNumber
    orderDirection: asc
    where: { blockNumber_gt: $lastBlock }
  ) {
    id
    blockNumber
    blockTimestamp
    transactionHash
  }
}
```

Do not advance a cursor until all pages have been processed. Use event IDs,
transaction/log identity, or a documented overlap strategy in addition to block
numbers where the source supports it.

## Troubleshooting

### Rate limiting or HTTP failures

The adapter retries its decorated request function up to three times with a
two-second backoff. It does not currently send `GRAPH_API_KEY`, and GraphQL
error payloads are not explicitly surfaced when a response contains no usable
`data`. Inspect application logs and the ingestion log rather than assuming an
empty result means the source is caught up.

### Stale or conflicting sync status

First inspect shared indexer state:

```bash
python3 -m services.ingestion.status indexers
python3 -m services.ingestion.status log --source subgraph --errors-only
```

Do not blindly update `chain_indexer_status`; reconcile the target rows and
protocol collision described in the cursor section before an operator-led
replay.

### Missing or inconsistent data

Check the source-specific ingestion records:

```bash
python3 -m services.ingestion.status log --source subgraph --limit 20
```

Then verify whether the data was produced by the legacy subgraph adapter, the
direct EAS indexer, or an RPC/Baal indexer. Different paths use different chain,
cursor, and lifecycle semantics.

## Verification Status

There are no dedicated subgraph-adapter tests currently covering CLI flags,
GraphQL errors, pagination, cursor advancement, schema mapping, UUID/chain
normalization, ClickHouse partial failure, or replay behavior. Generic ingestion
retry and reliability tests are not end-to-end validation of this adapter.

Relevant implementation and tests:

- Legacy adapter: `services/ingestion/subgraph_indexer.py`
- Direct EAS ingestion: `services/ingestion/eas_indexer.py`
- RPC governance ingestion: `services/ingestion/gnosis_indexer.py`, `services/ingestion/baal_indexer.py`
- Shared ingestion helpers: `services/ingestion/base.py`, `services/ingestion/config.py`
- Status CLI: `services/ingestion/status.py`
- Generic retry tests: `tests/test_ingestion_retry.py`, `tests/test_ingestion_reliability.py`
