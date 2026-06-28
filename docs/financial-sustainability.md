# Financial Sustainability

Kokonut tracks financial sustainability as governed evidence, not only as narrative. The model answers whether a farm is grant-dependent, transitioning, self-sustaining, or surplus-generating.

## Records

| Table | Purpose |
|---|---|
| `financial_sustainability_plan` | Farm-level sustainability strategy, revenue streams, grant dependency, reinvestment, public-goods allocation, runway, and projected NOI |
| `v_public_financial_sustainability_summary` | Public-safe published sustainability plans with evidence maturity labels |

## Farm Models

- `public_good_optimized`
- `blended`
- `for_profit`
- `cooperative`
- `research_pilot`
- `other`

## Governed Metrics

- `grant_dependency_pct`
- `reinvestment_rate_pct`
- `public_goods_allocation_pct`
- `sustainability_runway_months`

## Commands

```bash
python3 -m services.export.report_generator --type financial_sustainability --location-id UUID
python3 -m services.agents.resilience_agent --location-id UUID
```

Financial sustainability reports are planning evidence. They do not guarantee future revenue, grant availability, or market performance.
