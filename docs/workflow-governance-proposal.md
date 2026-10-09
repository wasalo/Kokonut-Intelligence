# Governance Proposal Lifecycle

Spec: `governance_proposal`

## Invariants

- Approved proposals require a human approver.
- Material harm and consent objections must be resolved before approval.
- Implementation requires a linked work item.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| approved_step | human reviewer | approved | Process approved | implementation work is complete | implement | implemented | implemented_step | transaction, human-approval |
| cancelled_step | circle participant | cancelled | Process cancelled | - | terminal | - | - | terminal |
| draft_step | circle participant | draft | Process draft | proposal withdrawn | cancel | cancelled | cancelled_step | entry |
| draft_step | circle participant | draft | Process draft | invalid proposal | reject | rejected | rejected_step | entry |
| draft_step | circle participant | draft | Process draft | proposal has a proposer and evidence | submit | submitted | submitted_step | entry |
| implemented_step | human reviewer | implemented | Process implemented | - | terminal | - | - | transaction, human-approval, terminal |
| in_review_step | circle participant | in_review | Process in_review | human approval and review gates clear | approve | approved | approved_step | - |
| in_review_step | circle participant | in_review | Process in_review | review rejects proposal | reject | rejected | rejected_step | - |
| in_review_step | circle participant | in_review | Process in_review | new proposal replaces this one | supersede | superseded | superseded_step | - |
| rejected_step | circle participant | rejected | Process rejected | - | terminal | - | - | terminal |
| submitted_step | circle participant | submitted | Process submitted | objections and reviews begin | review | in_review | in_review_step | - |
| submitted_step | circle participant | submitted | Process submitted | human rejects proposal | reject | rejected | rejected_step | - |
| superseded_step | circle participant | superseded | Process superseded | - | terminal | - | - | terminal |

## Sources

- `schemas/postgres/246_governance_proposals.sql`

## Governance Controls

- Human approval requires material harm and consent objections to be resolved.
- Implementation requires a linked work item.

## Data and Persistence

- governance_proposal | evidence, objections, work item

## Audit Controls

- Lifecycle transitions are recorded with actor and timestamp.
- Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.

## Tests

- `tests/test_governance_proposals.py`

## Mermaid

```mermaid
flowchart TD
    approved_step[approved_step: Process approved [human reviewer]]
    cancelled_step((cancelled_step: Process cancelled [circle participant]))
    draft_step[draft_step: Process draft [circle participant]]
    implemented_step((implemented_step: Process implemented [human reviewer]))
    in_review_step[in_review_step: Process in_review [circle participant]]
    rejected_step((rejected_step: Process rejected [circle participant]))
    submitted_step[submitted_step: Process submitted [circle participant]]
    superseded_step((superseded_step: Process superseded [circle participant]))
    approved_step -->|implementation work is complete / implement -> implemented| implemented_step
    draft_step -->|proposal withdrawn / cancel -> cancelled| cancelled_step
    draft_step -->|invalid proposal / reject -> rejected| rejected_step
    draft_step -->|proposal has a proposer and evidence / submit -> submitted| submitted_step
    in_review_step -->|human approval and review gates clear / approve -> approved| approved_step
    in_review_step -->|review rejects proposal / reject -> rejected| rejected_step
    in_review_step -->|new proposal replaces this one / supersede -> superseded| superseded_step
    submitted_step -->|objections and reviews begin / review -> in_review| in_review_step
    submitted_step -->|human rejects proposal / reject -> rejected| rejected_step
```
