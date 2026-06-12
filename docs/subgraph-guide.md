# Subgraph Indexer Guide

The subgraph indexer queries external subgraphs to pull structured on-chain data into the Kokonut platform. It supports EAS attestation subgraphs and Kokonut-specific contract event subgraphs via The Graph.

## Overview

The indexer lives in `services/ingestion/subgraph_indexer.py` and periodically queries GraphQL endpoints hosted on The Graph's decentralized network. It:

- Fetches new attestations and schemas from the EAS subgraph
- Tracks Kokonut contract events (deposits, distributions, votes)
- Deduplicates records using block number tracking
- Logs all ingestion to `ingestion_log` and tracks sync state in `chain_indexer_status`

## Architecture

```
┌─────────────────────┐     GraphQL      ┌──────────────────────┐
│  subgraph_indexer.py │ ─────────────── │  The Graph Subgraph  │
│                     │                  │  (EAS / Kokonut)     │
└────────┬────────────┘                  └──────────────────────┘
         │
         ▼
┌─────────────────────┐     SQL          ┌──────────────────────┐
│  PostgreSQL          │ ◄─────────────  │  Canonical Tables    │
│                     │                  │  attestation_record  │
│                     │                  │  wallet_activity_event│
│                     │                  │  chain_indexer_status │
└─────────────────────┘                  └──────────────────────┘
```

### Data Flow

1. Indexer reads last synced block from `chain_indexer_status`
2. Queries subgraph for records after that block
3. Normalizes response to canonical schema
4. Upserts into target tables
5. Updates `chain_indexer_status` with new block number

## Configuration

Environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `EAS_GRAPHQL_URL` | `https://attest.sh` | EAS GraphQL API endpoint |
| `GRAPH_API_KEY` | _(empty)_ | The Graph API key for paid subgraphs |
| `ETH_RPC_URL` | `https://ethereum.publicnode.com` | Ethereum mainnet RPC |
| `OPTIMISM_RPC_URL` | `https://mainnet.optimism.io` | Optimism RPC |
| `BASE_RPC_URL` | `https://mainnet.base.org` | Base RPC |

Subgraph endpoints are configured in `SUBGRAPH_ENDPOINTS` within the indexer:

```python
SUBGRAPH_ENDPOINTS = {
    "eas": "https://api.studio.thegraph.com/query/eas/attestations/v0.0.1",
    "eas_schema": "https://api.studio.thegraph.com/query/eas/schemas/v0.0.1",
}
```

## Supported Protocols

### EAS (Ethereum Attestation Service)

Queries the EAS subgraph for:

- **Attestations**: On-chain claims with schema, attester, recipient, and data
- **Schema Registrations**: Schema definitions created by Kokonut or partners
- **Revocations**: Attestation revocation events

### Kokonut Contract Events

Queries Kokonut-specific subgraphs for:

- **Treasury Events**: Inflows and outflows from farm wallets
- **Governance Events**: Proposals, votes, delegation changes
- **Digital Lego Usage**: Protocol interactions tied to farms

## Running the Indexer

### CLI Usage

```bash
# Index all supported protocols
python3 -m services.ingestion.subgraph_indexer

# Index only EAS data
python3 -m services.ingestion.subgraph_indexer --protocol eas

# Dry run (no writes)
python3 -m services.ingestion.subgraph_indexer --dry-run

# Index from a specific block
python3 -m services.ingestion.subgraph_indexer --from-block 120000000
```

### Querying Indexed Data

```python
import psycopg2

conn = psycopg2.connect(host="localhost", dbname="kokonut_intelligence", user="kokonut")
cur = conn.cursor()

# Get recent attestations
cur.execute("""
    SELECT ar.attestation_uid, ar.claim_type, ar.status, ar.chain,
           ars.name as schema_name, ar.created_at
    FROM attestation_record ar
    JOIN attestation_schema ars ON ar.schema_id = ars.id
    ORDER BY ar.created_at DESC
    LIMIT 10
""")
for row in cur.fetchall():
    print(row)
```

### Checking Sync Status

```sql
SELECT chain, indexer_type, last_synced_block, last_synced_at, status
FROM chain_indexer_status
ORDER BY updated_at DESC;
```

## Extending: Adding New Subgraph Sources

### Step 1: Define the GraphQL Query

Add a new query constant in `subgraph_indexer.py`:

```python
MY_PROTOCOL_QUERY = """
query GetEvents($lastBlock: Int!, $first: Int!) {
    protocolEvents(
        first: $first
        orderBy: blockNumber
        orderDirection: asc
        where: { blockNumber_gt: $lastBlock }
    ) {
        id
        blockNumber
        blockTimestamp
        eventType
        amount
        participant
        # ... other fields
    }
}
"""
```

### Step 2: Add the Subgraph Endpoint

```python
SUBGRAPH_ENDPOINTS["my_protocol"] = "https://api.studio.thegraph.com/query/my-org/my-protocol/v0.0.1"
```

### Step 3: Implement the Fetch Function

```python
def fetch_my_protocol_events(session, last_block, batch_size=100):
    """Fetch events from My Protocol subgraph."""
    events = []
    offset = 0
    while True:
        resp = session.post(
            SUBGRAPH_ENDPOINTS["my_protocol"],
            json={"query": MY_PROTOCOL_QUERY, "variables": {"lastBlock": last_block, "first": batch_size}},
        )
        data = resp.json()
        batch = data.get("data", {}).get("protocolEvents", [])
        if not batch:
            break
        events.extend(batch)
        offset += batch_size
        if len(batch) < batch_size:
            break
    return events
```

### Step 4: Implement the Normalize Function

```python
def normalize_my_protocol_event(raw):
    """Normalize a raw subgraph event to canonical schema."""
    return {
        "source_system": "my_protocol",
        "source_id": raw["id"],
        "event_type": raw["eventType"],
        "amount": raw["amount"],
        "chain": "optimism",
        "block_number": int(raw["blockNumber"]),
        "block_timestamp": raw["blockTimestamp"],
        "metadata": raw,
    }
```

### Step 5: Wire into the Main Indexer

```python
def main():
    # ... existing code ...
    if args.protocol in ("all", "my_protocol"):
        print("Indexing My Protocol events...")
        events = fetch_my_protocol_events(session, last_block)
        # ... upsert logic ...
```

## Troubleshooting

### "Rate limited" errors

The Graph free tier has rate limits. Use a paid API key:

```bash
export GRAPH_API_KEY=your-api-key-here
```

### Stale sync status

Reset the indexer to re-sync from a known good block:

```sql
UPDATE chain_indexer_status
SET last_synced_block = 120000000, status = 'syncing'
WHERE chain = 'optimism' AND indexer_type = 'subgraph';
```

### Missing data after indexing

Check the ingestion log for errors:

```sql
SELECT source_system, status, error_message, created_at
FROM ingestion_log
WHERE source_system = 'subgraph'
ORDER BY created_at DESC
LIMIT 20;
```
