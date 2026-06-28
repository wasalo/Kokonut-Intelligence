# Regenerative Outcomes And Stewardship

Kokonut tracks reviewer-facing regenerative outcomes as governed summaries over canonical source tables. The module makes ecological and social outcomes easier to review without replacing detailed source evidence.

## Records

| Table | Purpose |
|---|---|
| `regenerative_outcome_summary` | Concise ecological and social outcomes: hectares, species, soil carbon, trees, roles, training, beneficiaries, confidence |
| `community_governance_mechanism` | Public decision methods, power distribution, participation cadence, veto/escalation paths |
| `replication_readiness_assessment` | Region/context readiness, prerequisites, barriers, enablers, support structures, evidence gates |
| `adaptive_stewardship_review` | Review cadence, trigger thresholds, corrective actions, completion, role ownership, continuity plan |

## Public Views

| View | Public Filter |
|---|---|
| `v_public_regenerative_outcome_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |
| `v_public_community_governance_mechanism` | Published, evidence maturity >= 3, non-empty public summary, registry-backed when location-scoped |
| `v_public_replication_readiness_summary` | Published, evidence maturity >= 3, non-empty public summary |
| `v_public_adaptive_stewardship_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |

## Governed Metrics

- `hectares_restored`
- `species_diversity_delta`
- `soil_carbon_delta_t_ha`
- `tree_survival_rate_pct`
- `community_governance_participation_pct`
- `replication_readiness_score`
- `adaptive_stewardship_action_completion_pct`

## Commands

```bash
python3 -m services.export.report_generator --type regenerative_outcomes --location-id UUID
python3 -m services.export.report_generator --type community_governance --location-id UUID
python3 -m services.export.report_generator --type replication_readiness --location-id UUID
python3 -m services.export.report_generator --type adaptive_stewardship --location-id UUID
python3 -m services.agents.regenerator_agent --location-id UUID
```

Outcome summaries are grant-reviewer evidence. Source tables remain canonical, and replication readiness is never an unlimited-scaling claim.
