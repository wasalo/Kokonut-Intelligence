# Farm Activity Lifecycle

Spec: `farm_activity`

## Invariants

- A farm activity begins in draft, created by a farmer or field worker.
- Farm activities require source_system, source_id, and source_raw for data lineage.
- Verification confirms the activity occurred and data is accurate; the verifier must differ from the submitter.
- Publication is a separate, explicit human-approved action and makes the activity available for governed metric computation.
- Rejection requires a reason and an explicit human disposition: request correction or close as an exception.
- Agents may draft or submit but may not verify or publish farm activities.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| fa_draft_entry | farmer | draft | Record farm activity | submit for verification | submit | submitted | fa_review_submitted | entry |
| fa_publish | human publisher | published | Explicitly publish verified activity | - | terminal | - | - | human-approval, terminal |
| fa_reject_submitted | human reviewer | rejected | Record reasoned disposition for submitted activity | exception or withdrawal; close without publication | close exception | rejected | fa_reject_terminal | human-approval |
| fa_reject_submitted | human reviewer | rejected | Record reasoned disposition for submitted activity | correctable issue; return to submitter | request correction | draft | fa_rework | human-approval |
| fa_reject_terminal | human reviewer | rejected | Terminal exception or withdrawal with retained reason | - | terminal | - | - | terminal |
| fa_reject_verified | human reviewer | rejected | Record reasoned disposition for verified activity | exception; close without publication | close exception | rejected | fa_reject_terminal | human-approval |
| fa_reject_verified | human reviewer | rejected | Record reasoned disposition for verified activity | correctable issue; return to submitter | request correction | draft | fa_rework | human-approval |
| fa_review_submitted | human reviewer | submitted | Independently review submitted activity | activity needs correction or exception disposition | reject | rejected | fa_reject_submitted | human-approval |
| fa_review_submitted | human reviewer | submitted | Independently review submitted activity | activity occurred and data is accurate | verify | verified | fa_verify | human-approval |
| fa_rework | farmer | draft | Correct rejected activity and resubmit | correction is ready for review | resubmit | submitted | fa_review_submitted | - |
| fa_verify | human publisher | verified | Decide whether to publish verified activity | verified activity is explicitly approved for governed use | publish | published | fa_publish | human-approval |
| fa_verify | human publisher | verified | Decide whether to publish verified activity | data inaccurate or requires correction | reject | rejected | fa_reject_verified | human-approval |

## Sources

- `schemas/postgres/003_operations.sql`
- `schemas/postgres/179_lifecycle_transition.sql`
- `schemas/postgres/381_mobile_consent_form_revisions.sql`
- `schemas/seeds/140_mobile_forms.sql`
- `services/mobile/api.py`
- `services/gateway/operator_mobile_review.py`

## Governance Controls

- The verifier must differ from the submitter.
- Publication is a separate explicit human-approved action; agents may not verify or publish.
- Rejection requires a reason and an explicit rework or exception disposition.
- Operational parent context must agree with location, plot, and crop cycle constraints.

## Data and Persistence

- farm_activity | location, plot, crop cycle, source lineage

## Audit Controls

- source_system, source_id, and source_raw preserve ingestion provenance.
- Lifecycle transitions must retain the operator actor and timestamp.

## Tests

- `tests/test_metrics.py`
- `tests/test_relational_integrity.py`
- `tests/test_workflow_specs.py`

## Mermaid

```mermaid
flowchart TD
    fa_draft_entry[fa_draft_entry: Record farm activity [farmer]]
    fa_publish((fa_publish: Explicitly publish verified activity [human publisher]))
    fa_reject_submitted[fa_reject_submitted: Record reasoned disposition for submitted activity [human reviewer]]
    fa_reject_terminal((fa_reject_terminal: Terminal exception or withdrawal with retained reason [human reviewer]))
    fa_reject_verified[fa_reject_verified: Record reasoned disposition for verified activity [human reviewer]]
    fa_review_submitted[fa_review_submitted: Independently review submitted activity [human reviewer]]
    fa_rework[fa_rework: Correct rejected activity and resubmit [farmer]]
    fa_verify[fa_verify: Decide whether to publish verified activity [human publisher]]
    fa_draft_entry -->|submit for verification / submit -> submitted| fa_review_submitted
    fa_reject_submitted -->|exception or withdrawal; close without publication / close exception -> rejected| fa_reject_terminal
    fa_reject_submitted -->|correctable issue; return to submitter / request correction -> draft| fa_rework
    fa_reject_verified -->|exception; close without publication / close exception -> rejected| fa_reject_terminal
    fa_reject_verified -->|correctable issue; return to submitter / request correction -> draft| fa_rework
    fa_review_submitted -->|activity needs correction or exception disposition / reject -> rejected| fa_reject_submitted
    fa_review_submitted -->|activity occurred and data is accurate / verify -> verified| fa_verify
    fa_rework -->|correction is ready for review / resubmit -> submitted| fa_review_submitted
    fa_verify -->|verified activity is explicitly approved for governed use / publish -> published| fa_publish
    fa_verify -->|data inaccurate or requires correction / reject -> rejected| fa_reject_verified
```
