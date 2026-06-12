# Attestation Guide

This document explains how Kokonut Intelligence uses the Ethereum Attestation Service (EAS) for on-chain verification of farm data.

## What is EAS?

The [Ethereum Attestation Service (EAS)](https://attest.sh/) is a decentralized protocol for making attestations on Ethereum and L2s. An attestation is a signed claim about anything — a harvest event, a soil measurement, a financial record — that is anchored on-chain and publicly verifiable.

Key concepts:

- **Schema**: Defines the structure of an attestation (field names and types)
- **Attestation**: A specific instance of a schema, signed by an attester and addressed to a recipient
- **Revocation**: An attestation can be revoked if it was made in error

## How Kokonut Uses EAS

Kokonut uses EAS to create verifiable claims about:

- Harvest quantity and quality (MRV claims)
- Financial summaries (NOI, revenue, costs)
- Environmental outcomes (soil carbon, biodiversity)
- Partner compliance and audit trails

### Workflow

```
Register Schema → Create Claim → Verify → Publish On-Chain → Query Attestations
```

1. **Register Schema** — Define what fields the attestation will contain
2. **Create Claim** — Build a claim from operational data (harvest, expense, etc.)
3. **Verify** — Human or agent review before on-chain submission
4. **Publish On-Chain** — Submit the signed attestation to EAS on Optimism/Base and mark the lifecycle record as published
5. **Query Attestations** — Retrieve and display verified claims

## Database Schema

### `attestation_schema`

Stores registered EAS schemas.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `schema_uid` | VARCHAR(66) | EAS schema UID (0x...) |
| `name` | VARCHAR(255) | Human-readable name |
| `description` | TEXT | What this schema attests |
| `schema_text` | TEXT | Raw EAS schema definition |
| `chain` | VARCHAR(50) | Chain where schema is registered |
| `resolver_address` | VARCHAR(42) | Optional EAS resolver contract |
| `version` | INTEGER | Schema version number |
| `active` | BOOLEAN | Whether schema is in use |

### `attestation_record`

Stores individual attestation claims and their on-chain status.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `attestation_uid` | VARCHAR(66) | On-chain attestation UID |
| `schema_id` | UUID | FK to `attestation_schema` |
| `claim_type` | VARCHAR(100) | `mrv`, `financial`, `operational`, `impact`, `identity` |
| `subject_id` | UUID | ID of the thing being attested about |
| `subject_type` | VARCHAR(100) | `location`, `harvest_event`, `crop_cycle`, etc. |
| `claim_data` | JSONB | The attestation payload |
| `evidence_hash` | VARCHAR(255) | Hash of supporting evidence |
| `evidence_cids` | TEXT[] | IPFS CIDs for evidence |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |
| `chain` | VARCHAR(50) | Chain where attested |
| `tx_hash` | VARCHAR(66) | On-chain transaction hash |
| `attested_at` | TIMESTAMPTZ | When attested on-chain |

### `attestation_request`

Stores request metadata before an attestation is signed or submitted. This lets MRV, report, and value-flow records move through review without exposing private evidence.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `subject_type` | VARCHAR(100) | Subject table/type such as `mrv_event` |
| `subject_id` | UUID | Subject record ID |
| `event_type` | VARCHAR(100) | `mrv_submission`, `impact_report`, `value_flow`, `agent_task` |
| `payload_cid` | TEXT | Public payload CID/reference |
| `payload_hash` | VARCHAR(64) | SHA-256 hash of public payload |
| `private_payload_hash` | VARCHAR(64) | SHA-256 hash of private payload, never the raw payload |
| `execution_status` | VARCHAR(50) | `pending`, `submitted`, `confirmed`, `failed`, `cancelled` |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |

## Using the EAS Indexer

The indexer pulls attestations from the EAS GraphQL API into `attestation_record`.

### Run the Indexer

```bash
# Index from Optimism (default)
python3 -m services.ingestion.eas_indexer --chain optimism

# Index from Base
python3 -m services.ingestion.eas_indexer --chain base

# Dry run
python3 -m services.ingestion.eas_indexer --dry-run
```

### What It Does

1. Queries EAS GraphQL for attestations addressed to Kokonut wallets
2. Normalizes attestation data to the `attestation_record` schema
3. Creates or updates `attestation_schema` entries for new schemas
4. Logs ingestion to `ingestion_log`
5. Updates sync state in `chain_indexer_status`

## Preparing Private-Data Requests Locally

Use `services.attestation` to prepare public metadata and hashes. The helper does not sign transactions and does not submit to EAS.

```bash
python3 -m services.attestation \
  --subject-type mrv_event \
  --subject-id MRV_EVENT_UUID \
  --event-type mrv_submission \
  --payload-file public-mrv.json \
  --private-payload-file private-evidence.json \
  --chain optimism \
  --pin-local
```

The command returns `payload_cid`, `payload_hash`, and `private_payload_hash`. Store those fields in `attestation_request`; keep `private-evidence.json` in controlled off-chain storage.

## API Examples

### Query Attestations via Directus REST

```bash
# All published harvest MRV claims
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8055/items/attestation_record?filter[status][eq]=published&filter[claim_type][eq]=mrv&fields[]=*&sort[]=-attested_at"

# Attestations for a specific harvest event
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8055/items/attestation_record?filter[subject_id][eq]=HARVEST_UUID&fields[]=*,schema_id.name"

# Attestation schemas
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8055/items/attestation_schema?filter[active][eq]=true&fields[]=name&fields[]=schema_text&fields[]=chain"
```

### Query via Directus GraphQL

```graphql
query {
  attestation_record(
    filter: { status: { _eq: "published" }, claim_type: { _eq: "mrv" } }
    sort: ["-attested_at"]
    limit: 10
  ) {
    id
    attestation_uid
    claim_data
    chain
    tx_hash
    attested_at
    schema_id {
      name
      chain
    }
  }
}
```

## Adding New Attestation Schemas

### Step 1: Define the Schema

Create an EAS-compatible schema definition:

```python
# Example: Soil carbon measurement attestation
SOIL_CARBON_SCHEMA = "uint256 locationId, uint256 carbonTonnesPerHa, uint256 measurementDate, string methodology, address lab"
```

### Step 2: Register in the Database

```sql
INSERT INTO attestation_schema (schema_uid, name, description, schema_text, chain, active)
VALUES (
    '0x...',
    'Soil Carbon Measurement',
    'Attests to soil carbon measurements from certified labs.',
    'uint256 locationId, uint256 carbonTonnesPerHa, uint256 measurementDate, string methodology, address lab',
    'optimism',
    true
);
```

### Step 3: Create Claims

```python
claim_data = {
    "locationId": 1,
    "carbonTonnesPerHa": 42,
    "measurementDate": 1719792000,
    "methodology": "WCB-v2.1",
    "lab": "0x1234...abcd",
}

# Insert draft attestation
INSERT INTO attestation_record (
    schema_id, claim_type, subject_id, subject_type,
    claim_data, status, chain
) VALUES (
    'SCHEMA_UUID', 'impact', 'LOCATION_UUID', 'location',
    '{"locationId": 1, "carbonTonnesPerHa": 42}', 'draft', 'optimism'
);
```

### Step 4: Attest On-Chain

Once verified, submit via EAS SDK and update the record:

```sql
UPDATE attestation_record
SET status = 'published',
    attestation_uid = '0x...',
    tx_hash = '0x...',
    attested_at = NOW()
WHERE id = 'RECORD_UUID';
```

## Security Considerations

- Only authorized wallets can create attestations on behalf of Kokonut
- All attestation records are reviewed before on-chain submission
- Private MRV evidence should not be placed on-chain or in public database fields
- Store raw private evidence off-chain; store only hashes, CIDs, UIDs, chain labels, transaction hashes, and timestamps in public metadata
- Revoked on-chain attestations remain on-chain; store revocation metadata while keeping lifecycle status canonical
- Evidence hashes ensure data integrity between off-chain and on-chain
