# Impact Claim Lifecycle

Spec: `impact_claim`

## Invariants

- An impact claim begins in draft and requires evidence.
- Public impact claims require evidence maturity >= 4.
- Public carbon claims require evidence maturity 6, claim_type='third_party_verified_claim', and published status.
- Verification is a human decision; agents cannot verify claims.
- Rejection is terminal and requires a reason.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| ic_draft_entry | author | draft | Create impact claim | withdrawn before submission | reject | rejected | ic_reject_draft | entry |
| ic_draft_entry | author | draft | Create impact claim | submit for review | submit | submitted | ic_submit | entry |
| ic_publish | system | published | Terminal published claim | - | terminal | - | - | terminal |
| ic_reject_draft | reviewer | rejected | Terminal rejected claim | - | terminal | - | - | terminal |
| ic_reject_submitted | reviewer | rejected | Terminal rejected claim | - | terminal | - | - | terminal |
| ic_reject_verified | reviewer | rejected | Terminal rejected claim | - | terminal | - | - | terminal |
| ic_submit | author | submitted | Submit claim for review | insufficient evidence | reject | rejected | ic_reject_submitted | - |
| ic_submit | author | submitted | Submit claim for review | evidence reviewed and verified | verify | verified | ic_verify | - |
| ic_verify | reviewer | verified | Verify claim evidence | approved for publication | publish | published | ic_publish | human-approval |
| ic_verify | reviewer | verified | Verify claim evidence | evidence insufficient for publication | reject | rejected | ic_reject_verified | human-approval |

## Sources

- `schemas/postgres/031_impact_claims_and_cids.sql`
- `services/agents/tasks.py`

## Mermaid

```mermaid
flowchart TD
    ic_draft_entry[ic_draft_entry: Create impact claim [author]]
    ic_publish((ic_publish: Terminal published claim [system]))
    ic_reject_draft((ic_reject_draft: Terminal rejected claim [reviewer]))
    ic_reject_submitted((ic_reject_submitted: Terminal rejected claim [reviewer]))
    ic_reject_verified((ic_reject_verified: Terminal rejected claim [reviewer]))
    ic_submit[ic_submit: Submit claim for review [author]]
    ic_verify[ic_verify: Verify claim evidence [reviewer]]
    ic_draft_entry -->|withdrawn before submission / reject -> rejected| ic_reject_draft
    ic_draft_entry -->|submit for review / submit -> submitted| ic_submit
    ic_submit -->|insufficient evidence / reject -> rejected| ic_reject_submitted
    ic_submit -->|evidence reviewed and verified / verify -> verified| ic_verify
    ic_verify -->|approved for publication / publish -> published| ic_publish
    ic_verify -->|evidence insufficient for publication / reject -> rejected| ic_reject_verified
```
