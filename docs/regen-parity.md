# Regen Network Compatibility

Kokonut Intelligence provides a PostgreSQL/Directus compatibility model for selected Regen Network data standards, ecocredit concepts, metadata concepts, and Data module v2 concepts. This is schema and service parity, not a claim of complete Regen blockchain-module interoperability.

Canonical records remain in PostgreSQL/Directus. Local CLI operations write governed database records. EAS anchoring, external registry recognition, cross-chain token movement, and other on-chain execution require separate configured flows and human approval.

## CreditClassInfo Compatibility

The local `credit_class` model and related tables represent the CreditClassInfo concepts:

| Regen concept | Local implementation |
|---|---|
| Name and description | `credit_class.name`, `credit_class.description` |
| URL | `credit_class.url` |
| Primary impact | `primary_impact_type`, `primary_impact_name`, `primary_impact_sdgs` |
| Co-benefits | `credit_class_cobenefit` |
| Source registries | `credit_class_registry` |
| Crediting program | `crediting_program` |
| Credit protocol | `credit_protocol` |
| Approved methodologies | `credit_class_methodology` |
| Crediting period | `crediting_period_years` |
| Eligible environment types | `ecosystem_types` |
| Eligible activities | `eligible_activities` |
| Buffer-pool accounts | `buffer_pool_account` |

Additional local fields include methodology version/reference, credit type and credit type ID, registry slug, issuer wallet, governance mechanism, approval requirement, admin address, allowlist requirement, chain, attestation UID, metadata, and governed lifecycle status.

Supported local credit types are `carbon`, `biodiversity`, `water`, `soil`, and `mixed`. Credit classes use `draft`, `submitted`, `verified`, `published`, and `deprecated` states. These records do not by themselves establish an on-chain Regen credit class, external methodology approval, or registry acceptance.

`get_class_full()` returns the class record together with its co-benefits, registries, programs, protocols, methodologies, and buffer pools. Related records remain separate PostgreSQL entities.

## ProjectInfo Compatibility

The metadata service builds a ProjectInfo-style view from a location, verified/published farm registry record, project links, project reference IDs, app metadata, partner role records, and the current IRI:

| ProjectInfo concept | Current implementation |
|---|---|
| Name and description | `location.name`, `location.description` |
| URL and project dates | `project_url`, `project_start_date`, `project_end_date` |
| Region and ecological context | `region`, `sub_region`, `bioregion`, `biome_type`, `watershed`, `sub_watershed` |
| Coordinates | `location.latitude`, `location.longitude` |
| Links | `project_link` and `links` response field |
| External references | `project_reference_id` and `referenceIds` response field |
| Developer, monitor, operator, owner | Verified/published `farm_registry_record` role IDs resolved through `partner` |
| Registry context | Verified/published `farm_registry_record` returned as `registry` |
| App metadata | `app_metadata` returned as `appMetadata` |
| Stable identifier | Current `iri_registry` IRI |

The current ProjectInfo response does not expose every Regen concept as a dedicated top-level field. Project size, feature geometry, environment type, activity, primary impact, co-benefits, project partner, and methodology may exist in related source tables or credit-class records but are not all assembled into the current `get_project_info()` response. Do not describe those concepts as fully API-exposed without checking the current response implementation.

Project role resolution intentionally uses a verified or published farm registry record. An unverified registry record is not used to populate the public ProjectInfo view.

Resolve the current ProjectInfo-style metadata through the IRI/metadata service:

```bash
python3 -m services.metadata_api.cli resolve \
  --iri "kokonut:location:UUID:v1"
```

The FastAPI metadata service also exposes:

```text
GET /data/v2/metadata-graph/{iri}
GET /data/v2/entity/{entity_type}/{entity_id}
GET /marketplace/v1/project/{location_id}
```

## Data Module v2 Compatibility

| Concept | Local implementation | Boundary |
|---|---|---|
| IRI | `iri_registry`, format `kokonut:{entity_type}:{entity_id}:v{version}` | Sequential registry versioning, not automatically content-addressed |
| Content hash | `content_hash_entry` plus optional `iri_registry.content_hash` | Local hash metadata; does not prove content publication |
| Resolver | `data_resolver` and `data_resolver_registration` | Local URL/manager registration; no external resolver guarantee |
| IRI attestor | `data_iri_attestor` | Local per-IRI attestor tracking |
| Metadata anchor | `anchor_metadata()` and `attestation_request` | Creates a pending anchor request and records chain metadata |
| EAS attestation | Separate attestation service and configured EAS flow | Signing/submission is not performed by `data_iri_attestor` |

Content hashes support `sha256`, `blake2b256`, and `sha512`, with `raw` and `graph` content types. Optional metadata includes media type, canonicalization algorithm, and Merkle-tree classification. The IRI resolver’s graph content classification does not currently perform RDF URDNA2015 canonicalization; the separate data-module content-hash records preserve richer algorithm metadata.

The data-module CLI is:

```bash
# Compute a hash without creating a record
python3 -m services.data_module.cli hash \
  --data "test" --algorithm sha256 --type raw

# Create and find content-hash records
python3 -m services.data_module.cli content-hash create \
  --iri-id UUID --hash HASH --algorithm sha256 --type raw
python3 -m services.data_module.cli content-hash find --hash HASH

# Define and register a resolver
python3 -m services.data_module.cli resolver define \
  --url "https://api.example/data" --manager 0xMANAGER
python3 -m services.data_module.cli resolver register \
  --resolver-id UUID --iri-id UUID
python3 -m services.data_module.cli resolver by-iri --iri-id UUID

# Record local IRI attestor state
python3 -m services.data_module.cli attest do \
  --iri-id UUID --attestor 0xATTESTOR
python3 -m services.data_module.cli attest list --iri-id UUID
```

`attest do` records local attestor state. It is not equivalent to signing and submitting an EAS attestation. Use the attestation CLI and human-approved wallet flow for EAS operations.

## Regen Data Standards

The following values are represented by database constraints or reference data:

| Concept | Values |
|---|---|
| `ClaimType` | `ecological`, `social`, `financial`, `governance`, `biocultural` |
| `VerificationStatus` | `self_reported`, `peer_reviewed`, `verified`, `ledger_anchored`, `withdrawn` |
| `VerdictType` | `pending`, `approved`, `rejected`, `needs_info` |
| `CreditGenerationMethod` | `avoided_emissions`, `carbon_dioxide_removal`, `emissions_reduction` |
| `MarketType` | `compliance`, `voluntary` |
| Partner `EntityType` | `individual`, `organization`, `community` |
| `QuantityUnit` | tonne, hectare, kilogram, cubic metre, kilometre, unit, percentage, gram, litre |

Additional parity fields include:

- `impact_claim.supersedes_id` for claim lineage;
- `attestation_record.verdict`, rationale, reviewed evidence, and graph IRI;
- `credit_class.credit_generation_method`, permanence period, and permanence flag;
- `credit_batch.market_type` and `batch_sequence`;
- `farm_registry_record.project_verifier_id`;
- partner entity type and wallet address.

Nullable parity fields remain nullable where the underlying record does not contain the corresponding standard concept. A local enum or check constraint does not imply complete protocol behavior or external validation.

## Credit, Batch, And Ecocredit Operations

The local credit hierarchy is:

```text
credit_type -> credit_class -> credit_batch -> carbon_credit
```

Credit classes define methodology and eligibility. Batches scope a class to a location and vintage, track quantities and evidence, and use governed status. Individual carbon-credit records link back to the class and batch.

Additional local ecocredit parity includes:

- authorized class issuers and creator allowlists;
- credit balances and supply calculations;
- credit baskets, deposits, tokens, and withdrawal behavior;
- sell orders, buy orders, allowed denominations, and marketplace execution;
- bridge transaction records.

Examples:

```bash
python3 -m services.credit_class.cli class create \
  --name "Kokonut Carbon" --methodology "IPCC 2006" \
  --type carbon --url "https://example.com"

python3 -m services.credit_class.cli batch create \
  --class-id UUID --location-id UUID --vintage 2026 --quantity 100
python3 -m services.credit_class.cli batch issue \
  --batch-id UUID --issuer 0xISSUER
python3 -m services.credit_class.cli batch balance --batch-id UUID

python3 -m services.credit_class.cli enrollment apply \
  --location-id UUID --class-id UUID
python3 -m services.credit_class.cli enrollment evaluate \
  --enrollment-id UUID --issuer 0xISSUER --status accepted

python3 -m services.credit_class.cli basket create \
  --name "Carbon Basket" --denom cusd
python3 -m services.credit_class.cli marketplace sell \
  --batch-id UUID --seller 0xSELLER --quantity 50 \
  --price 2500 --denom cusd
```

## Bridge Boundary

Bridge operations create local `credit_bridge_transaction` records:

```bash
python3 -m services.credit_class.cli bridge out \
  --batch-id UUID --sender 0xSENDER --target celo \
  --recipient 0xRECIPIENT --quantity 50
python3 -m services.credit_class.cli bridge in \
  --class-id UUID --source polygon --issuer 0xISSUER \
  --recipient 0xRECIPIENT --quantity 100
python3 -m services.credit_class.cli bridge complete \
  --bridge-tx-id UUID
```

Outbound creation checks available batch quantity and configured allowed target chains, defaulting to `celo` and `gnosis`. Completion records a bridge transaction hash when supplied. These functions do not themselves lock/mint/burn external chain tokens or prove a completed cross-chain transfer. External bridge execution and reconciliation remain separate operational responsibilities.

## Attestation And Publication Boundaries

- Credit-class, batch, claim, registry, and bridge records use local governed lifecycle states.
- Agents and automated services cannot replace required human verification or publication approval.
- A local `verified` or `published` row does not establish external registry recognition.
- EAS metadata, UIDs, and transaction hashes are evidence references; they do not replace claim-specific external verification.
- Private evidence and signing keys remain offchain/private. Public metadata should contain hashes, CIDs, UIDs, chain labels, transaction hashes, and timestamps only.

## References And Verification

- Credit class and batch schema: `schemas/postgres/103_credit_class_batch.sql`
- ProjectInfo support: `schemas/postgres/108_project_info.sql`
- Ecocredit parity: `schemas/postgres/109_ecocredit_parity.sql`
- Data module v2: `schemas/postgres/110_data_v2_parity.sql`
- Regen standards: `schemas/postgres/112_regen_standards_parity.sql`
- Credit class services: `services/credit_class/`
- ProjectInfo service: `services/metadata_api/project_info.py`
- Metadata resolver/API: `services/metadata_api/`
- IRI service: `services/iri/`
- Data module service: `services/data_module/`
- Attestation service: `services/attestation/`
- Linked-data tests: `tests/test_linked_data.py`
- Attestation tests: `tests/test_attestation.py`
- Credit-class tests: `tests/test_linked_data.py` and `tests/test_carbon_credits.py`

Run the linked-data and attestation checks with:

```bash
PYTHONPATH=. uv run pytest tests/test_linked_data.py tests/test_attestation.py -v
```
