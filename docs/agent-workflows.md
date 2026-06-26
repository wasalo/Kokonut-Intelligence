# Agent Workflows

Kokonut agents support Green Paper V1 review tasks without bypassing governance. Agents can prepare draft outputs, exports, and summaries, but they cannot verify or publish their own records.

## Task Catalogue

The task catalogue lives in `services/agents/tasks.py`.

| Task | Purpose | Writes | Risk |
|---|---|---|---|
| `cids_export` | Prepare CIDS v3.2.0 Essential Tier JSON-LD for a location | None | Low |
| `feedback_synthesis` | Summarize public stakeholder feedback and aggregate private/no-consent signals | Optional `ai_summary:draft` | Medium |
| `public_interest_report_context` | Prepare limitations, evidence gaps, and public stakeholder voice for reports | None | Low |

## Commands

```bash
python3 -m services.agents.tasks --list
python3 -m services.agents.tasks --describe cids_export
python3 -m services.agents.cids_agent --location-id UUID --summary
python3 -m services.agents.feedback_agent --location-id UUID
python3 -m services.agents.feedback_agent --location-id UUID --store
```

## Safety Rules

- Agents may create draft outputs for human review.
- Agents may submit or reject their own outputs when allowed by workflow hooks.
- Agents may not verify or publish their own outputs.
- High-risk actions (`publish`, `attest`, `onchain_submit`, `delete`, `bulk_update`, `financial_write`, `status_change_to_published`) require human approval and audit logging.
- Feedback synthesis must not include raw private stakeholder feedback; private/no-consent records are aggregate-only.

## Output Schemas

Output schemas are intentionally lightweight dictionaries in `services/agents/tasks.py`. They validate required fields without replacing database constraints, Directus hooks, or human review.
