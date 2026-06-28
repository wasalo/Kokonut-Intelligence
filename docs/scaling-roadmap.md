# Scaling Roadmap

Kokonut treats scaling as a staged readiness process rather than an unlimited-growth claim. Roadmap milestones document required resources, partners, dependencies, and risk gates.

## Records

| Table | Purpose |
|---|---|
| `scaling_roadmap_milestone` | Network or farm-specific scaling milestone with target region, farm model, farm count, capital needed, dependencies, risk gates, and target date |
| `v_public_scaling_roadmap_summary` | Public-safe published scaling roadmap milestones |
| `green_paper_publication_review` | Review state, open questions, approvals, and publication proof metadata for Green Paper versions |
| `v_public_green_paper_publication_status` | Public-safe Green Paper publication status |

## Governed Metric

- `scaling_readiness_score`

## Commands

```bash
python3 -m services.export.report_generator --type scaling_roadmap --location-id UUID
python3 -m services.export.report_generator --type green_paper_publication_status --location-id UUID
python3 -m services.agents.resilience_agent --location-id UUID
```

Scaling roadmap entries are planning evidence. They are not commitments to launch farms unless capital, partner, operational, risk, and governance gates are satisfied.
