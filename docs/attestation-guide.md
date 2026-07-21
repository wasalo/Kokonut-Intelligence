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
- Bio-organic fertilizer batch production
- Data stream posts for environmental project tracking

### Workflow

```
Register Schema → Create Claim → Verify → Publish On-Chain → Query Attestations
```

1. **Register Schema** — Define what fields the attestation will contain
2. **Create Claim** — Build a claim from operational data (harvest, expense, etc.)
3. **Verify** — Human or agent review before on-chain submission
4. **Publish On-Chain** — Submit the signed attestation to EAS on Celo and mark the lifecycle record as published
5. **Query Attestations** — Retrieve and display verified claims

## Database Schema

### `attestation_schema`

Stores registered EAS schemas (`schemas/postgres/006_web3.sql:159-170`).

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
| `created_at` | TIMESTAMPTZ | When the schema was registered |

### `attestation_record`

Stores individual attestation claims and their on-chain status (`schemas/postgres/006_web3.sql:173-205`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `attestation_uid` | VARCHAR(66) | On-chain attestation UID (UNIQUE) |
| `schema_id` | UUID | FK to `attestation_schema` |
| `claim_type` | VARCHAR(100) | `mrv`, `financial`, `operational`, `impact`, `identity`, `harvest`, `compliance`, `bio_batch` |
| `subject_id` | UUID | ID of the thing being attested about |
| `subject_type` | VARCHAR(100) | `location`, `harvest_event`, `crop_cycle`, etc. |
| `claim_data` | JSONB | The attestation payload |
| `evidence_hash` | VARCHAR(255) | SHA-256 hash of supporting evidence |
| `evidence_cids` | TEXT[] | IPFS CIDs for evidence |
| `evidence_urls` | TEXT[] | URLs to supporting evidence files |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |
| `reviewer_id` | UUID | Who reviewed the attestation |
| `review_notes` | TEXT | Reviewer comments |
| `reviewed_at` | TIMESTAMPTZ | When reviewed |
| `chain` | VARCHAR(50) | Chain where attested |
| `tx_hash` | VARCHAR(66) | On-chain transaction hash |
| `attested_at` | TIMESTAMPTZ | When attested on-chain |
| `expiration_date` | DATE | Optional expiration date |
| `revocation_date` | DATE | When revoked (if applicable) |
| `schema_version` | VARCHAR(20) | Version of the schema used |
| `private_payload_hash` | VARCHAR(64) | SHA-256 hash of private payload (never raw data) |
| `payload_cid` | TEXT | Content identifier for offchain storage |
| `verdict` | VARCHAR(50) | Review verdict |
| `rationale` | TEXT | Reviewer rationale |
| `graph_iri` | TEXT | Linked data IRI for the attestation |
| `expires_at` | TIMESTAMPTZ | Optional expiration timestamp |
| `created_at` | TIMESTAMPTZ | When the record was created |
| `created_by` | UUID | Who created the record |

### `attestation_request`

Stores request metadata before an attestation is signed or submitted. This lets MRV, report, and value-flow records move through review without exposing private evidence (`schemas/postgres/013_prd_completion.sql:281-310`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `subject_type` | VARCHAR(100) | Subject table/type such as `mrv_event` |
| `subject_id` | UUID | Subject record ID |
| `mrv_event_id` | UUID | FK to `mrv_event` (if applicable) |
| `mrv_claim_id` | UUID | FK to `mrv_claim` (if applicable) |
| `report_snapshot_id` | UUID | FK to `report_snapshot` (if applicable) |
| `value_flow_id` | UUID | FK to `value_flow` (if applicable) |
| `schema_id` | UUID | FK to `attestation_schema` |
| `event_type` | VARCHAR(100) | `mrv_submission`, `impact_report`, `value_flow`, `agent_task` |
| `chain` | VARCHAR(50) | Target chain for on-chain submission |
| `payload_cid` | TEXT | Public payload CID/reference |
| `payload_hash` | VARCHAR(64) | SHA-256 hash of public payload |
| `private_payload_hash` | VARCHAR(64) | SHA-256 hash of private payload, never the raw payload |
| `attestor_role` | VARCHAR(100) | Role of the attester |
| `resolver_address` | VARCHAR(42) | EAS resolver contract address |
| `execution_status` | VARCHAR(50) | `pending`, `submitted`, `confirmed`, `failed`, `cancelled` |
| `attestation_uid` | VARCHAR(66) | On-chain attestation UID (filled after submission) |
| `tx_hash` | VARCHAR(66) | On-chain transaction hash (filled after submission) |
| `error_message` | TEXT | Error details if submission failed |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |
| `requested_by` | UUID | Who requested the attestation |
| `reviewed_by` | UUID | Who reviewed the request |
| `reviewed_at` | TIMESTAMPTZ | When reviewed |
| `submitted_at` | TIMESTAMPTZ | When submitted on-chain |
| `confirmed_at` | TIMESTAMPTZ | When confirmed on-chain |
| `metadata` | JSONB | Additional request metadata |
| `created_at` | TIMESTAMPTZ | When the request was created |
| `updated_at` | TIMESTAMPTZ | When the request was last updated |

## Using the EAS Indexer

The indexer pulls attestations from the EAS GraphQL API into `attestation_record`. It only indexes attestations addressed to wallets tracked in the `wallet_profile` table.

### Run the Indexer

```bash
# Index from Celo (primary Kokonut attestation chain)
python3 -m services.ingestion.eas_indexer --chain celo

# Index from supported secondary chains
python3 -m services.ingestion.eas_indexer --chain optimism
python3 -m services.ingestion.eas_indexer --chain base

# Index from all supported chains (omit --chain)
python3 -m services.ingestion.eas_indexer
```

The `--chain` argument accepts `optimism`, `base`, or `celo`. When omitted, the indexer processes all three chains.

### What It Does

1. Queries `wallet_profile` for tracked Kokonut wallets
2. Paginates EAS GraphQL per wallet per chain
3. Normalizes attestation data to the `attestation_record` schema
4. Creates or updates `attestation_schema` entries for new schemas
5. Dual-writes to PostgreSQL `attestation_record` and ClickHouse `attestation_events`
6. Updates sync state in `chain_indexer_status`

## Preparing Private-Data Requests Locally

Use `services.attestation.payload` to prepare public metadata and hashes. The helper does not sign transactions and does not submit to EAS.

```bash
python3 -m services.attestation.payload \
  --subject-type mrv_event \
  --subject-id MRV_EVENT_UUID \
  --event-type mrv_submission \
  --payload-file public-mrv.json \
  --private-payload-file private-evidence.json \
  --chain celo \
  --pin-local
```

The command returns `payload_cid`, `payload_hash`, and `private_payload_hash`. Store those fields in `attestation_request`; keep `private-evidence.json` in controlled off-chain storage.

### Sensitive Field Blocklist

The `validate_public_payload()` function rejects payloads containing fields from `SENSITIVE_PUBLIC_KEYS` (`services/attestation/payload.py:18-35`):

```
private_payload, raw_evidence, source_raw, receipt_image, image_blob,
file_blob, base64, secret, password, token, private_key, email, phone,
worker_name, customer_name, supplier_name
```

Public payloads are also validated to reject strings longer than 2048 characters and data URIs.

## Attestation Service Modules

The `services/attestation/` package contains 11 modules:

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| `cli.py` | CLI interface for schema, attest, revoke, query, info commands | `main()` |
| `config.py` | Chain configuration (Celo, Celo-Alfajores, Optimism, Base), contract addresses, constants | `EAS_CHAIN_CONFIG`, `get_chain_config()`, `KOKONUT_MULTISIG`, `ATTESTER_PRIVATE_KEY` |
| `schemas.py` | 7 Kokonut schema definitions and attestation data helpers | `KOKONUT_SCHEMAS`, `SCHEMA_DB_NAMES`, `prepare_*_attestation_data()` |
| `schema_encoder.py` | ABI encode/decode for EAS schema fields | `parse_schema()`, `encode_data()`, `decode_data()` |
| `eas_client.py` | Web3 contract wrapper for EAS interactions | `EASClient`: `register_schema()`, `get_schema()`, `attest()`, `multi_attest()`, `revoke()`, `get_attestation()`, `is_valid_attestation()` |
| `signer.py` | Wallet management and transaction signing | `EASSigner`: `estimate_and_send()`, `get_nonce()`, `get_balance_eth()` |
| `publisher.py` | High-level orchestration layer | `register_kokonut_schemas()`, `publish_attestation()`, `publish_batch()`, `revoke_attestation()`, `get_attestation()`, `get_schema()` |
| `offchain.py` | EIP-712 offchain attestation signing and verification | `sign_offchain_attestation()`, `verify_offchain_attestation()` |
| `payload.py` | Privacy-preserving request preparation | `prepare_attestation_request()`, `validate_public_payload()`, `SENSITIVE_PUBLIC_KEYS` |

## API Examples

### Query Attestations via Directus REST

```bash
DIRECTUS_URL=${DIRECTUS_URL:-https://localhost/directus}

# All published harvest MRV claims
curl -k -H "Authorization: Bearer $TOKEN" \
  "$DIRECTUS_URL/items/attestation_record?filter[status][eq]=published&filter[claim_type][eq]=mrv&fields[]=*&sort[]=-attested_at"

# Attestations for a specific harvest event
curl -k -H "Authorization: Bearer $TOKEN" \
  "$DIRECTUS_URL/items/attestation_record?filter[subject_id][eq]=HARVEST_UUID&fields[]=*,schema_id.name"

# Attestation schemas
curl -k -H "Authorization: Bearer $TOKEN" \
  "$DIRECTUS_URL/items/attestation_schema?filter[active][eq]=true&fields[]=name&fields[]=schema_text&fields[]=chain"
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
    'celo',
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
    '{"locationId": 1, "carbonTonnesPerHa": 42}', 'draft', 'celo'
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

## EAS on Celo

Celo is the primary chain for Kokonut attestations. EAS v1.3.0 is deployed on Celo mainnet.

### Deployed Contracts

| Contract | Address | Explorer |
|----------|---------|----------|
| EAS | `0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92` | [celoscan.io](https://celoscan.io/address/0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92) |
| SchemaRegistry | `0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34` | [celoscan.io](https://celoscan.io/address/0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34) |
| KokonutResolver | `0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad` | [celoscan.io](https://celoscan.io/address/0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad) |
| Kokonut Multisig | `0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5` | [celoscan.io](https://celoscan.io/address/0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5) |

### Kokonut Schemas

| Schema | UID | Use Case | Active |
|--------|-----|----------|--------|
| `kokonut-mrv` | `0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54` | MRV claims (location, crop, quantity, evidence) | Yes |
| `kokonut-impact` | `0xb99bb4b2a55218b8f4df1f0bd4c39400711809f13ef5d150d2903648c6590dfe` | Environmental impact (soil carbon, biodiversity, NDVI) | Yes |
| `kokonut-financial` | `0x75b42beb85dd852134dfaff3de41b8dc361ed0cb2bf93ce3009c8ec082de905b` | Financial summaries (NOI, revenue, costs) | Yes |
| `kokonut-harvest` | `0xb359f9756e3cb3597e4048dccae2842083359906fbae8dc8c0e9af8ac1b3ccff` | Harvest verification (quantity, quality, date) | Yes |
| `kokonut-compliance` | `0x59632edcf1d04be0c2dcfd572282bbd4dac518e7a92872ec45ade29876ef95f5` | Partner compliance and audit trails | Yes |
| `kokonut-bio-batch` | `0x9306a4cf...38ff29` | Bio-organic fertilizer batch production (LAC) | Yes |
| `kokonut-data-post` | `0x0000...0000` | Data stream posts for environmental project tracking | No (not yet registered onchain) |

### Supported Chains

| Chain | Chain ID | EAS Address | Default |
|-------|----------|-------------|---------|
| Celo | 42220 | `0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92` | Yes |
| Celo-Alfajores | 44787 | `0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92` | No |
| Optimism | 10 | `0x4200000000000000000000000000000000000021` | No |
| Base | 8453 | `0x4200000000000000000000000000000000000021` | No |

### Attester Wallets

| Wallet | Address | Role |
|--------|---------|------|
| Deployer | `0x3394C45b5938127EB56603A6051dF26CFAF08C26` | Schema registration, initial attestations |
| Kokonut Multisig | `0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5` | Resolver owner, governance attestations |

### CLI Usage

```bash
# Show chain config and attester info
python3 -m services.attestation.cli info --chain celo

# List available schema definitions
python3 -m services.attestation.cli schema list

# Register a new schema onchain
python3 -m services.attestation.cli schema register \
  --name "My Schema" \
  --chain celo

# Get an onchain schema by UID
python3 -m services.attestation.cli schema get \
  --uid 0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54 \
  --chain celo

# Create an onchain attestation on Celo
python3 -m services.attestation.cli attest \
  --schema 0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54 \
  --recipient 0xRECIPIENT \
  --data '[{"name":"locationId","type":"string","value":"..."}]' \
  --chain celo

# Create a signed offchain attestation (no gas)
python3 -m services.attestation.cli offchain-attest \
  --schema 0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54 \
  --recipient 0xRECIPIENT \
  --data '[{"name":"locationId","type":"string","value":"..."}]' \
  --chain celo

# Revoke an attestation
python3 -m services.attestation.cli revoke \
  --schema 0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54 \
  --uid 0xATTESTATION_UID \
  --chain celo

# Query an attestation from onchain
python3 -m services.attestation.cli query --uid 0xATTESTATION_UID --chain celo
```

## Offchain Attestations

Offchain attestations are EIP-712 signed messages that can be verified without gas. They are useful for:

- High-frequency attestations where gas cost is prohibitive
- Attestations that need to be shared privately before being anchored onchain
- Lightweight verification workflows

The `offchain-attest` CLI command returns a signed JSON object. It does not write to `attestation_record` — the signature can be verified independently using `verify_offchain_attestation()` from `services/attestation/offchain.py`.

## Private Data

Private MRV evidence stays offchain. The attestation stores only:

- `evidenceHash`: SHA-256 hash of the private payload
- `payloadCid`: Content identifier for offchain storage (local dev uses `local://sha256/<hash>`)

The `prepare_attestation_request()` function in `services/attestation/payload.py` separates public and private payloads, hashes the private data, and validates that the public payload does not leak sensitive fields.

For selective disclosure, EAS supports Merkle-tree-based private data attestations where only specific fields are revealed. This is available via the EAS SDK `PrivateData` class.

For full zero-knowledge privacy (proving facts about data without revealing it), Noir ZK circuits can be used. This is a future enhancement.

## Security Considerations

- Only authorized wallets can create attestations on behalf of Kokonut
- The KokonutResolver gates attestation to allowed attesters (deployer + Kokonut multisig)
- All attestation records are reviewed before on-chain submission
- Private MRV evidence should not be placed on-chain or in public database fields
- Store raw private evidence off-chain; store only hashes, CIDs, UIDs, chain labels, transaction hashes, and timestamps in public metadata
- Revoked on-chain attestations remain on-chain; store revocation metadata while keeping lifecycle status canonical
- Evidence hashes ensure data integrity between off-chain and on-chain
- Resolver ownership should be transferred to the Kokonut multisig after deployment
- The `validate_public_payload()` function blocks sensitive field names from public payloads

## Testing

```bash
# Attestation tests (11 tests)
python3 -m tests.test_attestation

# Run CLI help verification
python3 -m services.attestation.cli --help
```

| Test | What It Validates |
|------|-------------------|
| `test_schema_encoder_roundtrip` | `encode_data` / `decode_data` / `parse_schema` roundtrip |
| `test_schema_encoder_types` | Encoding of address, int256, bytes32, string types |
| `test_chain_config` | `get_chain_config()` for celo, optimism, unsupported chain |
| `test_kokonut_schemas` | `list_schemas()` contains all 5 core schemas |
| `test_cli_help` | Subprocess `--help` output contains expected commands |
| `test_cli_schema_list` | `schema list` outputs schema names |
| `test_cli_info` | `info --chain celo` outputs chain_id and EAS address |
| `test_schema_db_name_mapping` | `SCHEMA_DB_NAMES` maps correctly |
| `test_abi_files_exist` | `EAS.json` and `SchemaRegistry.json` exist |
| `test_public_payload_rejects_sensitive_keys` | `prepare_attestation_request` rejects payloads with `private_payload` |
| `test_public_payload_accepts_hash_metadata` | `prepare_attestation_request` allows hash/CID metadata |
