# GNH Alignment And Inclusion

Kokonut tracks Gross National Happiness alignment as governed evidence. The module maps public-safe farm evidence to GNH domains while keeping cultural knowledge, vulnerable-group identity data, and cross-cultural readiness claims bounded.

## Records

| Table | Purpose |
|---|---|
| `gnh_alignment_assessment` | Domain-level GNH alignment score, strengths, gaps, and safeguards |
| `cultural_preservation_plan` | Cultural preservation, local-language, consent, and local-review planning |
| `renewable_energy_plan` | Planned or implemented renewable energy infrastructure, energy share, and conservative displacement estimates |
| `vulnerable_group_access_plan` | Group-level access barriers, accommodations, and participation pathways |
| `foundational_wellbeing_observation` | Public-safe happiness, peace, safety, basic-needs, dignity, and belonging signals |

## Public Views

| View | Public Filter |
|---|---|
| `v_public_gnh_alignment_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |
| `v_public_cultural_preservation_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |
| `v_public_renewable_energy_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |
| `v_public_vulnerable_access_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |
| `v_public_foundational_wellbeing_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |

## Governed Metrics

- `gnh_alignment_score`
- `cultural_preservation_activity_count`
- `local_language_access_coverage_pct`
- `renewable_energy_share_pct`
- `fossil_energy_displacement_estimate`
- `vulnerable_group_access_coverage_pct`
- `foundational_wellbeing_score`
- `peace_and_safety_signal`

## Commands

```bash
python3 -m services.export.report_generator --type gnh_alignment --location-id UUID
python3 -m services.export.report_generator --type cultural_preservation --location-id UUID
python3 -m services.export.report_generator --type renewable_energy --location-id UUID
python3 -m services.export.report_generator --type vulnerable_access --location-id UUID
python3 -m services.export.report_generator --type foundational_wellbeing --location-id UUID
python3 -m services.agents.gnh_agent --location-id UUID
```

GNH reports are alignment evidence, not Bhutan-readiness certification. Cross-cultural expansion requires local review and new governed records.
