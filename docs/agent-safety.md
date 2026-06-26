# Agent Safety

Kokonut agents assist with drafts, exports, synthesis, and review preparation. They do not replace human governance.

## Rules

- Agents can create draft outputs.
- Agents can submit or reject their own outputs where hooks allow it.
- Agents cannot verify or publish their own outputs.
- High-risk actions require human approval and audit logging.

High-risk actions are:

- `publish`
- `attest`
- `onchain_submit`
- `delete`
- `bulk_update`
- `financial_write`
- `status_change_to_published`

## Enforcement

- Database constraints in `schemas/postgres/029_impact_accountability_foundation.sql`.
- Directus hook rules in `extensions/kokonut-hooks/src/agent-safety.ts`.
- Python preflight helpers in `services/agents/safety.py`.
- Audit log flags in `agent_action_log.high_risk` and `agent_action_log.requires_human_approval`.

## Reviewer Responsibility

Reviewers may use agent outputs as evidence preparation, but final publication, attestation submission, and public claims remain human-approved decisions.
