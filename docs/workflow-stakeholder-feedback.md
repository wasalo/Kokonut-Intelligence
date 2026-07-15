# Stakeholder Feedback Lifecycle

Spec: `stakeholder_feedback`

## Invariants

- Stakeholder feedback is private by default.
- Public feedback requires consent_given=TRUE, public consent scope, status='published', and a non-empty public_summary.
- Verification requires a minimum 7-day review period after submission.
- Publication makes feedback publicly visible with redacted PII.
- Rejection is terminal and requires a reason.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| sf_draft_entry | stakeholder | draft | Record feedback | withdrawn before submission | reject | rejected | sf_reject_draft | entry |
| sf_draft_entry | stakeholder | draft | Record feedback | submit for review | submit | submitted | sf_submit | entry |
| sf_publish | system | published | Terminal published feedback | - | terminal | - | - | terminal |
| sf_reject_draft | reviewer | rejected | Terminal rejected feedback | - | terminal | - | - | terminal |
| sf_reject_submitted | reviewer | rejected | Terminal rejected feedback | - | terminal | - | - | terminal |
| sf_reject_verified | reviewer | rejected | Terminal rejected feedback | - | terminal | - | - | terminal |
| sf_submit | stakeholder | submitted | Submit feedback for review | rejected during review | reject | rejected | sf_reject_submitted | - |
| sf_submit | stakeholder | submitted | Submit feedback for review | 7-day review period elapsed, verified | verify | verified | sf_verify | - |
| sf_verify | reviewer | verified | Verify feedback and consent | approved for public display | publish | published | sf_publish | human-approval |
| sf_verify | reviewer | verified | Verify feedback and consent | rejected after verification | reject | rejected | sf_reject_verified | human-approval |

## Sources

- `schemas/postgres/030_stakeholder_feedback.sql`
- `services/agents/feedback_agent.py`

## Mermaid

```mermaid
flowchart TD
    sf_draft_entry[sf_draft_entry: Record feedback [stakeholder]]
    sf_publish((sf_publish: Terminal published feedback [system]))
    sf_reject_draft((sf_reject_draft: Terminal rejected feedback [reviewer]))
    sf_reject_submitted((sf_reject_submitted: Terminal rejected feedback [reviewer]))
    sf_reject_verified((sf_reject_verified: Terminal rejected feedback [reviewer]))
    sf_submit[sf_submit: Submit feedback for review [stakeholder]]
    sf_verify[sf_verify: Verify feedback and consent [reviewer]]
    sf_draft_entry -->|withdrawn before submission / reject -> rejected| sf_reject_draft
    sf_draft_entry -->|submit for review / submit -> submitted| sf_submit
    sf_submit -->|rejected during review / reject -> rejected| sf_reject_submitted
    sf_submit -->|7-day review period elapsed, verified / verify -> verified| sf_verify
    sf_verify -->|approved for public display / publish -> published| sf_publish
    sf_verify -->|rejected after verification / reject -> rejected| sf_reject_verified
```
