# Stakeholder Feedback

Stakeholder feedback is private by default. Public Green Paper outputs can include only consented summaries and aggregate review signals.

## Records

| Table | Purpose |
|---|---|
| `stakeholder_feedback` | Raw or summarized stakeholder feedback with consent, sentiment, themes, and maturity |
| `stakeholder_feedback_review` | Review, escalation, response, and publication trail |
| `v_public_stakeholder_feedback_summary` | Public-safe feedback summaries only |

## Public Exposure Rules

Public feedback requires all of the following:

- `consent_given = TRUE`
- `consent_scope` is `public_summary`, `public_quote`, or `public_full`
- `status = 'published'`
- `public_summary` is non-empty

Raw private feedback should not be included in public reports, CIDS exports, dashboards, or agent outputs.

## Review Workflow

Use `draft`, `submitted`, `verified`, `published`, and `rejected` for feedback lifecycle. Rejected feedback is retained for internal governance but excluded from public dashboards and summaries.

## Agent Synthesis

`services.agents.feedback_agent` summarizes public feedback and aggregates private/no-consent counts. With `--store`, it creates a draft `ai_summary` for human review.
