# Kokonut Commons Governance

Kokonut tracks anti-capture governance, flexible redistribution policies, federation protocols, algorithmic redistribution mechanisms, and participatory signals as governed evidence. Policies are scenario-specific so each farm, DAO, or network context can adapt allocation and governance rules without hardcoding one universal percentage.

## Records

| Table | Purpose |
|---|---|
| `anti_capture_governance_policy` | Voting caps, veto rights, Sybil resistance, enforcement mode, and anti-plutocratic safeguards |
| `commons_redistribution_policy` | Flexible current/proposed redistribution policies by scenario, revenue basis, trigger, and audit cadence |
| `federation_protocol` | Permissionless forking, local adaptation rights, mutual aid, shared infrastructure, and anti-extractive safeguards |
| `algorithmic_redistribution_mechanism` | Proposed, pilot, or active redistribution mechanisms with privacy safeguards and enforcement mode |
| `participatory_signal_experiment` | Advisory meme, vibes, story, sentiment, or ranked-preference experiments with safety boundaries |

## Commands

```bash
python3 -m services.export.report_generator --type anti_capture_governance --location-id UUID
python3 -m services.export.report_generator --type redistribution_policy --location-id UUID
python3 -m services.export.report_generator --type federation_mutual_aid --location-id UUID
python3 -m services.export.report_generator --type algorithmic_redistribution --location-id UUID
python3 -m services.export.report_generator --type participatory_signal --location-id UUID
python3 -m services.agents.kokonut_commons_agent --location-id UUID
```

Proposed redistribution scenarios are not commitments. Meme/vibes signals are advisory unless explicitly reviewed and cannot override evidence maturity, privacy, treasury, or human approval gates.
