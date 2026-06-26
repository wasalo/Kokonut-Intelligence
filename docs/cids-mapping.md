# CIDS Mapping

Kokonut targets Common Impact Data Standard (CIDS) v3.2.0 Essential Tier for Green Paper V1.

## Current Mapping

| Kokonut Source | CIDS Class | Notes |
|---|---|---|
| `location`, `farm` | `cids:Organization` | Uses farm/location name, description, and stable URI. |
| `farm_registry_record` | `cids:Program` | Represents the farm program/project profile. |
| `stakeholder_outcome` | `cids:Outcome`, `cids:StakeholderOutcome` | Connects outcome, stakeholder group, importance, and theme. |
| `stakeholder_feedback` | `cids:Stakeholder` support data | Private by default; public export uses summaries only. |
| `metric_definition` | `cids:Indicator` | Governed metric definition. |
| `metric_value` | `cids:IndicatorReport` | Verified metric values only. |
| `impact_claim` | `cids:ImpactReport` | Includes maturity, methodology, verifier, and attestation metadata. |
| `sdg` / `farm_impact_mapping` | `cids:Theme` | SDG theme URI uses `https://metadata.un.org/sdg/{number}`. |

## Export

Run:

```bash
python3 -m services.registry.cids_export --location-id UUID
```

The exporter emits JSON-LD with `kokonut:alignmentTier = essential` and `kokonut:cidsVersion = 3.2.0`.

## Compatibility Notes

- Public carbon claims require Evidence Maturity Level 6 before export as public claims.
- Private stakeholder feedback is not exported as public feedback.
- CIDS export is a compatibility layer; PostgreSQL/Directus remains canonical.
