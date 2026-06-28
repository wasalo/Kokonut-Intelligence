# Commons Liberation And Stewardship

Kokonut tracks commons-oriented claims as governed evidence rather than slogans. This layer answers whether farm operations are reducing operator burden, protecting community control over capital, broadening governance participation, and documenting land stewardship boundaries.

## Records

| Table | Purpose |
|---|---|
| `time_liberation_observation` | Workflow-level hours reclaimed, reporting-burden reduction, and automation or agent support observations |
| `capital_alignment_assessment` | Public-safe capital-source alignment, extractive-risk level, community-control terms, and reinvestment commitments |
| `governance_inclusion_observation` | Representation, missing groups, pseudonymous participation, and privacy-safe participation evidence |
| `land_stewardship_commitment` | Stewardship model, anti-speculation terms, community benefit rights, landlord-dependency risk, and commons transition path |

## Public Views

| View | Public Filter |
|---|---|
| `v_public_time_liberation_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |
| `v_public_capital_alignment_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |
| `v_public_governance_inclusion_summary` | Published, evidence maturity >= 3, non-empty public summary, registry-backed when location-scoped |
| `v_public_land_stewardship_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |

## Governed Metrics

- `operator_time_reclaimed_hours`
- `field_reporting_burden_reduction_pct`
- `aligned_capital_share_pct`
- `extractive_capital_risk_count`
- `governance_representation_coverage_pct`
- `pseudonymous_participation_enabled`
- `land_stewardship_commitment_count`
- `landlord_dependency_risk_level`

## Commands

```bash
python3 -m services.export.report_generator --type time_liberation --location-id UUID
python3 -m services.export.report_generator --type capital_alignment --location-id UUID
python3 -m services.export.report_generator --type governance_inclusion --location-id UUID
python3 -m services.export.report_generator --type land_stewardship --location-id UUID
python3 -m services.agents.commons_agent --location-id UUID
```

Commons reports do not expose private labor records, private capital terms, raw identity details, or legal land-transfer claims unless separately governed and publishable.
