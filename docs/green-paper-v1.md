# Green Paper V1 Integration Notes

Green Paper V1 should present Kokonut as an evidence-governed impact intelligence layer for regenerative syntropic farms, not as an unchecked claims engine.

## Included Capabilities

- CIDS v3.2.0 Essential Tier JSON-LD export.
- Evidence maturity levels across claims, feedback, MRV, and reporting.
- Private-by-default stakeholder feedback and public-safe summaries.
- Public impact claims with maturity gates.
- Level 6 external verification for public carbon claims.
- Evidence gap and stakeholder feedback dashboards.
- Report snapshots with public-interest context.
- Agent-assisted CIDS export and feedback synthesis with draft-only outputs.

## Suggested Narrative

Kokonut combines PostgreSQL/Directus governance, ClickHouse analytics, Celo EAS attestations, CIDS-compatible export, stakeholder consent, and agent-safe workflows. The system is designed to make regenerative farm evidence comparable while preserving privacy and surfacing uncertainty.

## Publication Boundaries

- CIDS export is compatibility mapping, not the canonical database.
- EAS attestations are verification metadata, not automatic proof of external verification.
- Carbon-balance evidence is distinct from carbon credit issuance.
- Private stakeholder evidence remains private unless explicit consent allows publication.
- Agent outputs are draft aids and must be human-reviewed.

## Green Paper Review Commands

```bash
./scripts/seed.sh
./scripts/seed-pilot.sh
./scripts/compute-metrics.sh
./scripts/verify-mvp.sh
python3 -m services.registry.cids_export --location-id UUID
python3 -m services.agents.feedback_agent --location-id UUID
python3 -m services.export.report_generator --auto --location-id UUID
```
