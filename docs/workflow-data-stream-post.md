# Data Stream Post Lifecycle

Spec: `data_stream_post`

## Invariants

- A data stream post begins in draft and requires a verified farm_registry_record for public visibility.
- Submission moves the post into the review pipeline.
- Verification is a human decision; agents cannot verify.
- Publication makes the post publicly visible and immutable.
- Rejection is terminal and requires a reason recorded in the lifecycle ledger.
- Blockchain anchoring uses the kokonut-data-post EAS schema on Celo.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| dsp_draft_entry | author | draft | Create data stream post | rejected before submission | reject | rejected | dsp_reject_draft | entry |
| dsp_draft_entry | author | draft | Create data stream post | submit for review | submit | submitted | dsp_submit | entry |
| dsp_publish | system | published | Terminal published post | - | terminal | - | - | terminal |
| dsp_reject_draft | reviewer | rejected | Terminal rejected post | - | terminal | - | - | terminal |
| dsp_reject_submitted | reviewer | rejected | Terminal rejected post | - | terminal | - | - | terminal |
| dsp_reject_verified | reviewer | rejected | Terminal rejected post | - | terminal | - | - | terminal |
| dsp_submit | author | submitted | Submit post for review | rejected during review | reject | rejected | dsp_reject_submitted | - |
| dsp_submit | author | submitted | Submit post for review | reviewed and verified | verify | verified | dsp_verify | - |
| dsp_verify | reviewer | verified | Verify post accuracy | approved for publication | publish | published | dsp_publish | human-approval |
| dsp_verify | reviewer | verified | Verify post accuracy | rejected after verification | reject | rejected | dsp_reject_verified | human-approval |

## Sources

- `schemas/postgres/100_data_stream.sql`
- `services/data_stream/cli.py`

## Mermaid

```mermaid
flowchart TD
    dsp_draft_entry[dsp_draft_entry: Create data stream post [author]]
    dsp_publish((dsp_publish: Terminal published post [system]))
    dsp_reject_draft((dsp_reject_draft: Terminal rejected post [reviewer]))
    dsp_reject_submitted((dsp_reject_submitted: Terminal rejected post [reviewer]))
    dsp_reject_verified((dsp_reject_verified: Terminal rejected post [reviewer]))
    dsp_submit[dsp_submit: Submit post for review [author]]
    dsp_verify[dsp_verify: Verify post accuracy [reviewer]]
    dsp_draft_entry -->|rejected before submission / reject -> rejected| dsp_reject_draft
    dsp_draft_entry -->|submit for review / submit -> submitted| dsp_submit
    dsp_submit -->|rejected during review / reject -> rejected| dsp_reject_submitted
    dsp_submit -->|reviewed and verified / verify -> verified| dsp_verify
    dsp_verify -->|approved for publication / publish -> published| dsp_publish
    dsp_verify -->|rejected after verification / reject -> rejected| dsp_reject_verified
```
