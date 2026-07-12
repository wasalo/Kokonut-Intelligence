# Regen Network Parity

## Overview

Kokonut Intelligence achieves full feature parity with Regen Network's data standards, ecocredit module, and data module v2.

## CreditClassInfo Parity

All 13 fields from Regen's `CreditClassInfo` schema are implemented:

| Regen Field | Implementation |
|------------|---------------|
| `name` | `credit_class.name` |
| `description` | `credit_class.description` |
| `url` | `credit_class.url` |
| `hasPrimaryImpact` | `credit_class.primary_impact_*` columns |
| `hasCoBenefits` | `credit_class_cobenefit` table |
| `hasSourceRegistry` | `credit_class_registry` table |
| `managedUnderProgram` | `crediting_program` table |
| `hasCreditProtocol` | `credit_protocol` table |
| `hasApprovedMethodologies` | `credit_class_methodology` table |
| `hasCreditingPeriod` | `credit_class.crediting_period_years` |
| `eligibleEnvironmentTypes` | `credit_class.ecosystem_types` |
| `eligibleActivities` | `credit_class.eligible_activities` |
| `hasBufferPoolAccounts` | `buffer_pool_account` table |

## ProjectInfo Parity

All 24 fields from Regen's `ProjectInfo` schema are implemented:

| Regen Field | Implementation |
|------------|---------------|
| `name` | `location.name` |
| `description` | `location.description` |
| `url` | `location.project_url` |
| `projectStartDate` | `location.project_start_date` |
| `projectEndDate` | `location.project_end_date` |
| `hasLinks` | `project_link` table |
| `hasReferenceId` | `project_reference_id` table |
| `hasFeature` | `location.boundary`/`center` (PostGIS) |
| `projectSize` | `farm.total_area` + `area_unit` |
| `environmentType` | `credit_class.ecosystem_types` |
| `region` | `location.region` |
| `bioregion` | `location.bioregion` |
| `biomeType` | `location.biome_type` |
| `watershed` | `location.watershed` |
| `subWatershed` | `location.sub_watershed` |
| `activity` | `credit_class.eligible_activities` |
| `hasPrimaryImpact` | `credit_class.primary_impact_*` |
| `hasCoBenefits` | `credit_class_cobenefit` table |
| `hasProjectDeveloper` | `farm_registry_record.developer_id` |
| `hasProjectMonitor` | `farm_registry_record.monitor_id` |
| `hasProjectOperator` | `farm_registry_record.operator_id` |
| `hasProjectOwner` | `farm_registry_record.owner_id` |
| `hasProjectPartner` | `partner` table |
| `usesMethodology` | `credit_class_methodology` table |

## Data Module v2 Parity

| Concept | Implementation |
|---------|---------------|
| IRI | `iri_registry` with `kokonut:{type}:{id}:v{version}` |
| Content Hash | `content_hash_entry` with raw/graph types |
| Resolver | `data_resolver` + `data_resolver_registration` |
| Attestor | `data_iri_attestor` per-IRI tracking |
| Anchor | EAS attestation + `anchor_iri()` |
| Attest | EAS signing + `attest_to_iri()` |

## Regen Data Standards Parity

| Enum | Values |
|------|--------|
| `ClaimType` | ecological, social, financial, governance, biocultural |
| `VerificationStatus` | self_reported, peer_reviewed, verified, ledger_anchored, withdrawn |
| `VerdictType` | pending, approved, rejected, needs_info |
| `CreditGenerationMethod` | avoided_emissions, carbon_dioxide_removal, emissions_reduction |
| `MarketType` | compliance, voluntary |
| `EntityType` | individual, organization, community |
| `QuantityUnit` | tonne, hectare, kg, m3, km, unit, %, g, L |

## CLI Commands

```bash
# Credit class with full parity
python3 -m services.credit_class.cli class create --name "Kokonut Carbon" --methodology "IPCC 2006" --type carbon --url "https://example.com"

# Enrollment workflow
python3 -m services.credit_class.cli enrollment apply --location-id UUID --class-id UUID
python3 -m services.credit_class.cli enrollment evaluate --enrollment-id UUID --issuer 0x1234 --status accepted

# Bridge operations
python3 -m services.credit_class.cli bridge out --batch-id UUID --sender 0x1234 --target celo --recipient 0x5678 --quantity 50
```
