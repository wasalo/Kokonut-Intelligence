# CIDS Mapping

Kokonut targets Common Impact Data Standard (CIDS) v3.2.0 Essential Tier for the Green Paper.

CIDS export is a compatibility layer; PostgreSQL/Directus remains canonical.

## Constants and configuration

| Constant | Value | Notes |
|---|---|---|
| `CIDS_VERSION` | `"3.2.0"` | Emitted as `kokonut:cidsVersion` in output |
| `CIDS_BASE_URL` | `https://kokonut.network/cids` | Override via `KOKONUT_CIDS_BASE_URL` env var |
| `CIDS_CONTEXTS` | Two JSON-LD context URIs | See below |
| `SDG_BASE_URL` | `https://metadata.un.org/sdg` | SDG theme `@id` prefix |

JSON-LD contexts:

```
https://ontology.commonapproach.org/contexts/cidsContext.jsonld
https://ontology.commonapproach.org/contexts/sffContext.jsonld
```

## Current Mapping

| Kokonut Source | CIDS Class | Notes |
|---|---|---|
| `location`, `farm` | `cids:Organization` | Uses farm/location name, description, and stable URI. |
| `farm_registry_record` | `cids:Program` | Represents the farm program/project profile. |
| `stakeholder_outcome` | `cids:Outcome`, `cids:StakeholderOutcome` | Connects outcome, stakeholder group, importance, and theme. |
| `stakeholder_feedback` | `cids:Stakeholder` support data | Private by default; public export uses summaries only. |
| `metric_definition` | `cids:Indicator` | Governed metric definition. |
| `metric_value` | `cids:IndicatorReport` | Verified metric values only. |
| EBF score metrics in `metric_value` | `cids:IndicatorReport` | EBF score outputs use Kokonut metadata (`kokonut:framework`, `kokonut:ebfPillar`); no new CIDS class. |
| `impact_claim` | `cids:ImpactReport` | Includes maturity, methodology, verifier, and attestation metadata. |
| `sdg` / `farm_impact_mapping` | `cids:Theme` | SDG theme URI uses `https://metadata.un.org/sdg/{number}`. |

## Unit mapping

The exporter normalizes Kokonut metric units to CIDS ontology unit URIs:

| Kokonut unit | CIDS ontology URI |
|---|---|
| `usd` | `cids#usd` |
| `cad` | `cids#cad` |
| `count` | `cids#countUnit` |
| `percentage` / `percent` / `%` | `cids#percent` |
| `kg` / `kilogram` | `cids#kilogram` |
| `tco2e` / `tonnes_co2e` | `cids#tonneCO2e` |
| `tonnes` | `cids#tonne` |
| (anything else) | `cids#unspecifiedUnit` |

## JSON-LD output structure

`export_location()` returns:

```json
{
  "@context": [
    "https://ontology.commonapproach.org/contexts/cidsContext.jsonld",
    "https://ontology.commonapproach.org/contexts/sffContext.jsonld"
  ],
  "@graph": [ ... ],
  "kokonut:cidsVersion": "3.2.0",
  "kokonut:alignmentTier": "essential"
}
```

The `@graph` array contains CIDS Essential Tier JSON-LD entities. `None` values are stripped recursively from the output.

## Graph builder: CIDS classes

The exporter queries 6 SQL result sets (location, stakeholder outcomes, framework mappings, metric values, stakeholder feedback, impact claims) and builds these CIDS classes:

### `cids:Organization`

Source: `location` + `farm` + `farm_registry_record`

| Field | Source |
|---|---|
| `hasName` | `farm_name` or `location.name` |
| `hasLegalName` | `farm_name` or `location.name` |
| `hasDescription` | `farm_description` or `location.description` |
| `hasProgram` | link to `cids:Program` |
| `hasOutcome` | links to `cids:Outcome` |
| `hasIndicator` | links to `cids:Indicator` |
| `hasStakeholder` | links to `cids:Stakeholder` |

### `cids:Program`

Source: `farm_registry_record`

| Field | Source |
|---|---|
| `hasName` | `project_summary` or `"{name} farm program"` |
| `hasDescription` | `proposed_solution` or `location.description` |
| `forOrganization` | link to `cids:Organization` |
| `hasImpactModel` | link to `cids:ImpactPathway` |

### `cids:ImpactPathway`

Source: computed from location

| Field | Source |
|---|---|
| `hasName` | `"{name} impact pathway"` |
| `hasDescription` | `local_problem` or default |
| `forOrganization` | link to `cids:Organization` |
| `hasOutcome` | links to `cids:Outcome` |
| `hasIndicator` | links to `cids:Indicator` |

### `cids:Theme`

Source: `sdg` via `farm_impact_mapping` (deduplicated by SDG number)

| Field | Source |
|---|---|
| `hasName` | `sdg_name` or `"SDG {number}"` |
| `hasDescription` | `"UN Sustainable Development Goal {number}"` |
| `hasCode` | `["https://metadata.un.org/sdg/{number}"]` |

### `cids:Stakeholder`

Source: distinct stakeholder groups from `stakeholder_outcome` + `stakeholder_feedback`

| Field | Source |
|---|---|
| `hasName` | stakeholder group name, title-cased |
| `forOrganization` | link to `cids:Organization` |

### `cids:Outcome`

Source: `stakeholder_outcome`

| Field | Source |
|---|---|
| `hasName` | `outcome_name` |
| `hasDescription` | `outcome_description` |
| `forOrganization` | link to `cids:Organization` |
| `forTheme` | link to `cids:Theme` (SDG) |
| `hasStakeholderOutcome` | link to `cids:StakeholderOutcome` |

### `cids:StakeholderOutcome`

Source: `stakeholder_outcome`

| Field | Source |
|---|---|
| `hasName` | `outcome_name` |
| `hasDescription` | `outcome_description` |
| `forStakeholder` | link to `cids:Stakeholder` |
| `forOutcome` | link to `cids:Outcome` |
| `hasImportance` | `importance` (high/moderate/low/neutral/unimportant/unknown) |
| `isUnderserved` | boolean |
| `hasImpactManagementNormsDefinition` | `importance_perspective` |

### `cids:Indicator`

Source: `metric_value` joined to `metric_definition` (deduplicated by indicator)

| Field | Source |
|---|---|
| `hasName` | `display_name` |
| `hasDescription` | `description` |
| `unit_of_measure` | normalized unit URI |
| `forOrganization` | link to `cids:Organization` |
| `hasIndicatorReport` | links to `cids:IndicatorReport` |
| `hasComment` | `"Kokonut governed metric definition"` |
| `kokonut:framework` | `"ebf"` when metric key starts with `ebf_` |
| `kokonut:ebfPillar` | extracted pillar name (e.g., `soil_health`) |

### `cids:IndicatorReport`

Source: `metric_value` (one per verified metric value)

| Field | Source |
|---|---|
| `hasName` | `"{location} - {display_name}"` |
| `value` | `i72:Measure` with `hasNumericalValue` and `unit_of_measure` |
| `startedAtTime` | ISO timestamp from `period_start` |
| `endedAtTime` | ISO timestamp from `period_end` |
| `forIndicator` | link to `cids:Indicator` |
| `forOrganization` | link to `cids:Organization` |
| `hasComment` | `computation_method` |
| `kokonut:framework` | `"ebf"` when metric key starts with `ebf_` |
| `kokonut:ebfPillar` | extracted pillar name |
| `kokonut:cidsMapping` | `"metric_value -> cids:IndicatorReport"` (EBF only) |

### `cids:ImpactReport`

Source: `impact_claim`

| Field | Source |
|---|---|
| `hasName` | `claim_text` (truncated to 120 chars) |
| `hasDescription` | `claim_text` |
| `forOrganization` | link to `cids:Organization` |
| `startedAtTime` | ISO timestamp from `period_start` |
| `endedAtTime` | ISO timestamp from `period_end` |
| `hasComment` | `confidence_notes` |
| `kokonut:evidenceMaturity` | integer level |
| `kokonut:evidenceMaturityLabel` | label string |
| `kokonut:methodologyRef` | methodology reference |
| `kokonut:externalVerifier` | external verifier name |
| `kokonut:attestationUid` | attestation UID (if any) |

## EBF metadata

EBF score metrics are registered with `cids_indicator_report` in their `report_usage` array:

- `ebf_air_quality_score`
- `ebf_water_management_score`
- `ebf_soil_health_score`
- `ebf_biodiversity_score`
- `ebf_carbon_sequestration_score`
- `ebf_equity_community_score`
- `ebf_implementation_quality_score`
- `ebf_overall_score`

In the exported JSON-LD, EBF `cids:IndicatorReport` entries include:
- `kokonut:framework` = `"ebf"`
- `kokonut:ebfPillar` = pillar name (e.g., `soil_health`, `overall`)
- `kokonut:cidsMapping` = `"metric_value -> cids:IndicatorReport"`

EBF score outputs should be represented as `cids:IndicatorReport` through governed `metric_value` rows rather than a new CIDS class.

## RDF/Linked Data integration

CIDS predicates are used in the RDF triple store for evidence chaining and credit/claim provenance.

Namespace: `CIDS_NS = "https://ontology.commonapproach.org/cids#"`

### Credit graph predicates

Used in `services/rdf/graph_builder.py` `build_credit_graph()`:

| Predicate | Field |
|---|---|
| `cids:creditCode` | `carbon_credit.credit_code` |
| `cids:vintageYear` | `carbon_credit.vintage_year` |
| `cids:methodology` | `carbon_credit.methodology` |
| `cids:issuableQuantity` | `carbon_credit.issuable_tonnes` |
| `cids:retiredQuantity` | `carbon_credit.retired_tonnes` |

### Claim graph predicates

Used in `services/rdf/graph_builder.py` `build_claim_graph()`:

| Predicate | Field |
|---|---|
| `cids:claimType` | `impact_claim.claim_type` |
| `cids:claimText` | `impact_claim.claim_text` |
| `cids:claimValue` | `impact_claim.claim_value` |
| `cids:hasEvidence` | links to evidence CID IRI |

### Evidence chain predicates

Used in `services/rdf/evidence_chain.py` `build_evidence_chain()`:

| Predicate | Purpose |
|---|---|
| `cids:hasEvidence` | links claim to evidence CID |
| `cids:hasAttestation` | links claim to attestation UID |
| `cids:verifiedBy` | links claim to external verifier |
| `cids:indicates` | links claim to stakeholder outcome |

`verify_evidence_chain()` checks for `hasEvidence` + `location` triple presence to validate the chain.

## LinkML schemas

Three LinkML schemas declare the CIDS namespace prefix:

| Schema | CIDS usage |
|---|---|
| `impact_claim.linkml.yaml` | `cids:` prefix; `evidence_cid` field as `range: uri` |
| `credit_batch.linkml.yaml` | `cids:` prefix; `monitoring_report_cid`, `verification_report_cid` fields |
| `credit_class.linkml.yaml` | `cids:` prefix (aligns with Regen Network Framework) |

## Evidence maturity

The `evidence_maturity_level` table defines levels 0–6. Public claim thresholds:

| Level | Label | Public claims |
|---|---|---|
| 0 | `narrative_only` | no |
| 1 | `self_reported` | no |
| 2 | `structured_record` | no |
| 3 | `reviewed_record` | no |
| 4 | `evidence_linked` | yes (includes CIDs, hashes, URLs) |
| 5 | `attested_record` | yes (onchain/offchain attestation) |
| 6 | `externally_verified` | yes (requires external verification) |

### Public carbon claim constraints

Public carbon claims require all of:
- `evidence_maturity = 6`
- `claim_type = 'third_party_verified_claim'`
- `external_verifier` non-empty
- `methodology_ref` non-empty
- `status = 'published'`

### `evidence_cids` fields

IPFS CID arrays are stored on:
- `attestation_record.evidence_cids` — attestation evidence CIDs
- `impact_bounty_submission.evidence_cids` — bounty submission evidence CIDs

Private evidence stays offchain. Only hashes, CIDs, UIDs, chain labels, tx hashes, and timestamps appear in public metadata.

## Export

### CLI

```bash
python3 -m services.registry.cids_export --location-id UUID
```

The exporter emits JSON-LD with `kokonut:alignmentTier = essential` and `kokonut:cidsVersion = 3.2.0`.

### Agent

```bash
python3 -m services.agents.cids_agent --location-id UUID --summary
```

The agent wraps the canonical exporter as a read-only task. It calls `assert_agent_action_allowed("read", "cids_export", ...)` and validates output against the `cids_export` schema in `services/agents/tasks.py`.

Output fields: `document`, `graph_count`, `alignment_tier`, `cids_version`.

`--summary` prints only `graph_count`, `alignment_tier`, `cids_version` (not the full JSON-LD).

### Agent task schema

```python
"cids_export": {
    "description": "Prepare a CIDS v3.2.0 Essential Tier JSON-LD export for one location.",
    "risk": "low",
    "inputs": {"location_id": {"type": "string", "format": "uuid", "required": True}},
    "outputs": {
        "document": {"type": "object", "required": True},
        "graph_count": {"type": "integer", "required": True},
        "alignment_tier": {"type": "string", "required": True},
        "cids_version": {"type": "string", "required": True},
    },
    "writes": [],
    "high_risk": False,
}
```

This is a pure read-only task with no database mutations.

### Service catalogue

`cids_agent` v1.0.0 is registered as an `agent` service in `schemas/postgres/195_service_catalog.sql`.

## Governance Boundary

CIDS export does not create or publish canonical records. Directus/PostgreSQL lifecycle state, evidence maturity, consent fields, and public-safe views determine what may appear in partner-facing outputs.

## Compatibility Notes

- Public carbon claims require Evidence Maturity Level 6 before export as public claims.
- Public EBF carbon pillar score outputs require Level 6 before public EBF reporting.
- EBF scorecards map to `cids:IndicatorReport` through verified `metric_value` rows rather than a new CIDS class.
- Private stakeholder feedback is not exported as public feedback.
- CIDS export is a compatibility layer; PostgreSQL/Directus remains canonical.

## Testing

```bash
python3 -m tests.test_cids_export
python3 -m tests.test_ebf_cids
python3 -m tests.test_ebf_p0
python3 -m tests.test_ebf_p1
python3 -m tests.test_ebf_p2
```

| Test file | Coverage |
|---|---|
| `test_cids_export.py` | Essential tier classes present, EBF metadata on IndicatorReports, export wraps with version/tier |
| `test_ebf_cids.py` | EBF scores export as `cids:IndicatorReport` (not `cids:EBFScorecard`) |
| `test_ebf_p0.py` | Seed registers `cids_indicator_report` in metric definitions |
| `test_ebf_p1.py` | Asserts `cids:IndicatorReport` appears in exported `cids_mapping` |
| `test_ebf_p2.py` | `docs/cids-mapping.md` documents EBF IndicatorReport path with correct phrases |
