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
| EBF score metrics in `metric_value` | `cids:IndicatorReport` | EBF score outputs use Kokonut metadata (`kokonut:framework`, `kokonut:ebfPillar`); no new CIDS class. |
| `impact_claim` | `cids:ImpactReport` | Includes maturity, methodology, verifier, and attestation metadata. |
| `sdg` / `farm_impact_mapping` | `cids:Theme` | SDG theme URI uses `https://metadata.un.org/sdg/{number}`. |

## Export

Run:

```bash
python3 -m services.registry.cids_export --location-id UUID
```

The exporter emits JSON-LD with `kokonut:alignmentTier = essential` and `kokonut:cidsVersion = 3.2.0`.

Agent-assisted export is available as a read-only task:

```bash
python3 -m services.agents.cids_agent --location-id UUID --summary
```

The agent wraps the same canonical exporter and validates required output fields from `services/agents/tasks.py`.

## Essential Tier Classes

The current exporter emits these CIDS-compatible classes when source data exists:

- `cids:Organization`
- `cids:Program`
- `cids:ImpactPathway`
- `cids:Stakeholder`
- `cids:StakeholderOutcome`
- `cids:Outcome`
- `cids:Indicator`
- `cids:IndicatorReport`
- `cids:ImpactReport`
- `cids:Theme`

## Governance Boundary

CIDS export does not create or publish canonical records. Directus/PostgreSQL lifecycle state, evidence maturity, consent fields, and public-safe views determine what may appear in partner-facing outputs.

## Compatibility Notes

- Public carbon claims require Evidence Maturity Level 6 before export as public claims.
- Public EBF carbon pillar score outputs require Level 6 before public EBF reporting.
- EBF scorecards map to `cids:IndicatorReport` through verified `metric_value` rows rather than a new CIDS class.
- Private stakeholder feedback is not exported as public feedback.
- CIDS export is a compatibility layer; PostgreSQL/Directus remains canonical.
