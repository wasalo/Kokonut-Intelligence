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
