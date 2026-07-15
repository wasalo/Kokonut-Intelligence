# Insurance Claim Lifecycle

Spec: `insurance_claim`

## Invariants

- claim requires policy_id, type, amount, evidence
- verification confirms claim validity
- publication enables payout processing

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| ic_draft_entry | farmer | draft | Create insurance claim | withdrawn before submission | reject | rejected | ic_reject_draft | entry |
| ic_draft_entry | farmer | draft | Create insurance claim | submit for verification | submit | submitted | ic_submit | entry |
| ic_publish | system | published | Terminal published insurance claim | - | terminal | - | - | terminal |
| ic_reject_draft | reviewer | rejected | Terminal rejected insurance claim | - | terminal | - | - | terminal |
| ic_reject_submitted | reviewer | rejected | Terminal rejected insurance claim | - | terminal | - | - | terminal |
| ic_reject_verified | reviewer | rejected | Terminal rejected insurance claim | - | terminal | - | - | terminal |
| ic_submit | farmer | submitted | Submit insurance claim for review | insufficient evidence | reject | rejected | ic_reject_submitted | - |
| ic_submit | farmer | submitted | Submit insurance claim for review | claim evidence confirmed | verify | verified | ic_verify | - |
| ic_verify | reviewer | verified | Verify insurance claim validity | approved for payout processing | publish | published | ic_publish | human-approval |
| ic_verify | reviewer | verified | Verify insurance claim validity | claim invalid | reject | rejected | ic_reject_verified | human-approval |

## Sources

- `schemas/postgres/194_process_taxonomy_expansion.sql`

## Mermaid

```mermaid
flowchart TD
    ic_draft_entry[ic_draft_entry: Create insurance claim [farmer]]
    ic_publish((ic_publish: Terminal published insurance claim [system]))
    ic_reject_draft((ic_reject_draft: Terminal rejected insurance claim [reviewer]))
    ic_reject_submitted((ic_reject_submitted: Terminal rejected insurance claim [reviewer]))
    ic_reject_verified((ic_reject_verified: Terminal rejected insurance claim [reviewer]))
    ic_submit[ic_submit: Submit insurance claim for review [farmer]]
    ic_verify[ic_verify: Verify insurance claim validity [reviewer]]
    ic_draft_entry -->|withdrawn before submission / reject -> rejected| ic_reject_draft
    ic_draft_entry -->|submit for verification / submit -> submitted| ic_submit
    ic_submit -->|insufficient evidence / reject -> rejected| ic_reject_submitted
    ic_submit -->|claim evidence confirmed / verify -> verified| ic_verify
    ic_verify -->|approved for payout processing / publish -> published| ic_publish
    ic_verify -->|claim invalid / reject -> rejected| ic_reject_verified
```
