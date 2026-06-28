# Capital Efficiency And Utility

Kokonut tracks capital efficiency as governed scenario evidence. The module answers how much output, public-goods value, regenerative savings, governance speed, and capital-provider utility are visible from published records.

## Records

| Table | Purpose |
|---|---|
| `capital_efficiency_scenario` | Scenario-level capital deployed, output value, public-goods value, and leverage ratio |
| `regenerative_efficiency_observation` | Practice-level cost savings, incremental output, implementation cost, and payback signals |
| `governance_throughput_observation` | DAO/community proposal creation, decision, execution, and latency observations |
| `capital_provider_utility_scenario` | Public-safe sponsor, funder, DAO, buyer, or investor utility scenario with limitations |

## Public Views

| View | Public Filter |
|---|---|
| `v_public_capital_efficiency_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |
| `v_public_regenerative_efficiency_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |
| `v_public_governance_throughput_summary` | Published, evidence maturity >= 3, non-empty public summary, registry-backed when location-scoped |
| `v_public_capital_provider_utility_summary` | Published, evidence maturity >= 3, non-empty public summary, verified/published registry record |

## Governed Metrics

- `capital_efficiency_usd_per_output`
- `regenerative_cost_savings_pct`
- `practice_payback_months`
- `governance_decision_latency_days`
- `capital_leverage_ratio`
- `capital_provider_utility_score`

## Commands

```bash
python3 -m services.export.report_generator --type capital_efficiency --location-id UUID
python3 -m services.export.report_generator --type governance_throughput --location-id UUID
python3 -m services.export.report_generator --type capital_provider_utility --location-id UUID
python3 -m services.agents.capital_efficiency_agent --location-id UUID
```

Capital efficiency and utility reports are scenario evidence. They are not investment advice, securities offerings, or guaranteed return projections.
