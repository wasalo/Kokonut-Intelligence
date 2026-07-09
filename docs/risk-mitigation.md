# Risk Mitigation

Kokonut uses a governed risk register to make mitigation, insurance scope, oversight, technical support, and residual risk explicit.

## Records

| Table | Purpose |
|---|---|
| `risk_mitigation_register` | Material risks with mitigation strategy, owner, review cadence, insurance scope, oversight, technical support, and residual risk |
| `v_public_risk_mitigation_summary` | Public-safe published risk register entries |

## Risk Categories

- `climate`
- `market`
- `operational`
- `financial`
- `governance`
- `policy`
- `evidence_quality`
- `community`
- `technical`
- `other`

## Governed Metric

- `risk_mitigation_coverage_pct`

## Commands

```bash
python3 -m services.export.report_generator --type risk_mitigation --location-id UUID
python3 -m services.agents.resilience_agent --location-id UUID
```

Insurance details may remain private when policy documents include sensitive commercial or personal information. Public reports summarize insurance scope only when safe to publish.

---

## CRISP Risk Scoring

The CRISP (Carbon Risk Identification and Scoring Principles) engine provides five-factor internal risk intelligence for farms, adapted from Solid World's SW-CRISP framework.

### Five Risk Dimensions

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| Carbon Yield | 40% | Likelihood of meeting carbon/biomass yield targets via scenario modeling |
| Climate Catastrophe | 25% | Probability of drought, flood, heat, fire, storm, water stress |
| Policy & Legal | 15% | Certification, regulatory, carbon rights, land tenure, community alignment |
| Financial Viability | 10% | Revenue diversity, cost structure, liquidity, market price exposure |
| Implementation | 10% | Track record, team strength, network, transparency |

### Rating Scale

| Rating | Score | Meaning |
|--------|-------|---------|
| AAA | 91–100 | Prime — lowest risk |
| AA | 80–91 | Very low risk |
| A | 69–80 | Low risk |
| B | 44–69 | Neutral — moderate risk |
| C | 20–44 | High risk |
| D | 0–20 | Junk — highest risk |

### Adaptive Weights

Weights can be overridden per-location via `crisp_location_weight` to account for site-specific risk profiles (e.g., higher climate weight for drought-prone regions).

### Commands

```bash
# Individual dimension
python3 -m services.crisp --carbon-yield --location-id UUID
python3 -m services.crisp --climate --location-id UUID
python3 -m services.crisp --policy --location-id UUID
python3 -m services.crisp --financial --location-id UUID
python3 -m services.crisp --implementation --location-id UUID

# Composite rating
python3 -m services.crisp --composite --location-id UUID --period-start 2025-01-01 --period-end 2025-12-31

# Compute and persist
python3 -m services.crisp --rate --location-id UUID --period-start 2025-01-01 --period-end 2025-12-31

# Show weights
python3 -m services.crisp --weights --location-id UUID
```

### Database Tables

| Table | Purpose |
|-------|---------|
| `crisp_risk_dimension` | Dimension definitions with default weights |
| `crisp_location_weight` | Per-location weight overrides |
| `crisp_risk_assessment` | Master assessment per location per period |
| `crisp_carbon_yield_risk` | Carbon yield scenario detail |
| `crisp_climate_risk` | Climate hazard scoring detail |
| `crisp_policy_risk` | Policy & legal risk detail |
| `crisp_financial_risk` | Financial viability detail |
| `crisp_implementation_risk` | Implementation risk detail |
| `v_crisp_composite_rating` | Public composite view |
| `v_crisp_latest_assessment` | Latest assessment view |

Full methodology: `docs/crisp-risk-scoring.md`
