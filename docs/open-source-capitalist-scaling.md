# Open Source Capitalist Scaling

Kokonut tracks scaling economics, adoption barriers, downside stress tests, and open-source reuse as governed evidence. This layer answers reviewer questions about cost-per-farm, ROI, explicit scaling targets, market/adoption barriers, and perpetuity risks without converting planning evidence into guarantees.

## Records

| Table | Purpose |
|---|---|
| `farm_launch_unit_economics` | Launch unit economics: cost per farm, hectare, beneficiary, projected ROI, payback, assumptions, and confidence |
| `network_scaling_target` | Planned/conditional network scaling targets with capital required, farm count, beneficiaries, readiness, dependencies, and risk gates |
| `adoption_barrier_assessment` | Farmer onboarding, DAO, regulatory, cultural, market, technical, capital, and evidence-quality barriers with owner and mitigation plan |
| `perpetual_value_stress_test` | Down-cycle scenarios for revenue, cost, grant delay, yield shock, runway, NOI, solvency, and mitigation actions |
| `open_source_impact_artifact` | Reusable schemas, dashboards, reports, agents, contracts, playbooks, exports, and datasets with reuse signals |

## Public Views

| View | Public Filter |
|---|---|
| `v_public_farm_launch_unit_economics` | Published, evidence maturity >= 3, public summary, registry-backed when location-scoped |
| `v_public_network_scaling_target` | Published, evidence maturity >= 3, public summary |
| `v_public_adoption_barrier_assessment` | Published, evidence maturity >= 3, public summary, registry-backed when location-scoped |
| `v_public_perpetual_value_stress_test` | Published, evidence maturity >= 3, public summary, registry-backed when location-scoped |
| `v_public_open_source_impact_artifact` | Published, evidence maturity >= 3, public summary |

## Governed Metrics

- `farm_launch_cost_usd`
- `cost_per_planned_farm_usd`
- `projected_roi_pct`
- `cost_per_beneficiary_usd`
- `cost_per_hectare_restored_usd`
- `downside_runway_months`
- `adoption_barrier_resolution_pct`
- `open_source_artifact_reuse_count`

## Commands

```bash
python3 -m services.export.report_generator --type scaling_economics --location-id UUID
python3 -m services.export.report_generator --type adoption_barriers --location-id UUID
python3 -m services.export.report_generator --type perpetual_value_stress --location-id UUID
python3 -m services.export.report_generator --type open_source_impact --location-id UUID
python3 -m services.agents.open_source_capitalist_agent --location-id UUID
```

Planned farm counts are roadmap targets unless backed by separate registry records. ROI and payback are scenario evidence, not guaranteed returns or securities offerings.
