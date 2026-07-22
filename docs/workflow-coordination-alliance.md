# Coordination Alliance Governance Workflow

Spec: `coordination_alliance`

## Invariants

- Consultation records affected parties, consent boundaries, accessibility, and minority views.
- Due diligence records identity, contribution capacity, dependency risk, capture risk, and ecological safeguards.
- Approval requires a linked stakeholder decision or cooperative governance record and a human approver.
- Activation is a human-approved transition and does not authorize unrecorded legal, financial, or operational commitments.
- Review evaluates participation, contribution delivery, benefit distribution, harm, risk, and knowledge exchange.
- Suspension pauses activation when material risk, unresolved harm, or governance failure is detected.
- Termination is a human-reviewed terminal outcome with disposition and outstanding-obligation evidence.
- Renewal starts a new consultation cycle and must not silently extend the prior agreement.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| ca_activation | human operator | activation | Activate approved alliance controls | participants, commitments, and controls are active | activate | review | ca_review | transaction, external-side-effect, human-approval, high-risk |
| ca_activation | human operator | activation | Activate approved alliance controls | activation preconditions fail | terminate | termination | ca_terminate_activation | transaction, external-side-effect, human-approval, high-risk |
| ca_approval | human reviewer | approval | Approve alliance through stakeholder decision or cooperative governance | approval and separation of duties are complete | approve | activation | ca_activation | transaction, human-approval |
| ca_approval | human reviewer | approval | Approve alliance through stakeholder decision or cooperative governance | approval requires material redesign | revise | consultation | ca_consultation | transaction, human-approval |
| ca_approval | human reviewer | approval | Approve alliance through stakeholder decision or cooperative governance | approval is rejected without a viable redesign | terminate | termination | ca_terminate_approval | transaction, human-approval |
| ca_consultation | stakeholder coordinator | consultation | Consult affected and participating parties | consent, accessibility, and representation are documented | consulted | due_diligence | ca_due_diligence | - |
| ca_consultation | stakeholder coordinator | consultation | Consult affected and participating parties | consultation identifies unacceptable harm | terminate | termination | ca_terminate_consultation | - |
| ca_draft | coordination proposer | draft | Prepare alliance consultation | scope and participants are ready | consult | consultation | ca_consultation | entry |
| ca_draft | coordination proposer | draft | Prepare alliance consultation | no mandate or unsafe premise | terminate | termination | ca_terminate_draft | entry |
| ca_due_diligence | due diligence reviewer | due_diligence | Assess identity, capacity, dependency, capture, and ecological risk | evidence and mitigations are complete | due_diligence_complete | approval | ca_approval | - |
| ca_due_diligence | due diligence reviewer | due_diligence | Assess identity, capacity, dependency, capture, and ecological risk | material gaps require renewed consultation | revise | consultation | ca_consultation | - |
| ca_due_diligence | due diligence reviewer | due_diligence | Assess identity, capacity, dependency, capture, and ecological risk | risk cannot be acceptably mitigated | terminate | termination | ca_terminate_diligence | - |
| ca_renewal | human reviewer | renewal | Prepare a new alliance term | renewal requires fresh consent and scope review | renew | consultation | ca_consultation | transaction, human-approval |
| ca_renewal | human reviewer | renewal | Prepare a new alliance term | renewal is declined | terminate | termination | ca_terminate_renewal | transaction, human-approval |
| ca_review | human reviewer | review | Review participation, value, harms, risks, and learning | review recommends continuation with a new term | renew | renewal | ca_renewal | human-approval |
| ca_review | human reviewer | review | Review participation, value, harms, risks, and learning | material risk or unresolved harm requires pause | suspend | suspension | ca_suspension | human-approval |
| ca_review | human reviewer | review | Review participation, value, harms, risks, and learning | review recommends closure | terminate | termination | ca_termination_review | human-approval |
| ca_suspension | human reviewer | suspension | Suspend alliance activity and preserve obligations | corrective evidence is complete | resume_review | review | ca_review | transaction, human-approval |
| ca_suspension | human reviewer | suspension | Suspend alliance activity and preserve obligations | suspension cannot be safely resolved | terminate | termination | ca_terminate_suspension | transaction, human-approval |
| ca_terminate_activation | human reviewer | termination | Terminate before activation completes | - | terminal | - | - | terminal |
| ca_terminate_approval | human reviewer | termination | Terminate after approval review | - | terminal | - | - | terminal |
| ca_terminate_consultation | human reviewer | termination | Terminate after consultation | - | terminal | - | - | terminal |
| ca_terminate_diligence | human reviewer | termination | Terminate after due diligence | - | terminal | - | - | terminal |
| ca_terminate_draft | human reviewer | termination | Terminate alliance before consultation | - | terminal | - | - | terminal |
| ca_terminate_renewal | human reviewer | termination | Terminate after renewal decision | - | terminal | - | - | terminal |
| ca_terminate_suspension | human reviewer | termination | Terminate from suspension | - | terminal | - | - | terminal |
| ca_termination_review | human reviewer | termination | Terminate after review | - | terminal | - | - | terminal |

## Sources

- `schemas/postgres/235_coordination_strategy.sql`
- `schemas/postgres/236_coordination_workflow_integration.sql`
- `schemas/postgres/179_lifecycle_transition.sql`
- `services/analytics/stakeholder_decisions.py`
- `services/analytics/cooperative_governance.py`

## Governance Controls

- Consent, accessibility, minority views, and separation of duties are required for governed coordination.
- No workflow step creates an implicit community commitment.

## Data and Persistence

- coordination_alliance | participants, reviews, objectives, obligations

## Audit Controls

- Lifecycle transitions are recorded with actor and timestamp.
- Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.

## Tests

- `tests/test_coordination.py`
- `tests/test_coordination_governance.py`
- `tests/test_coordination_accounting.py`
- `tests/test_coordination_market_cycles.py`

## Mermaid

```mermaid
flowchart TD
    ca_activation[ca_activation: Activate approved alliance controls [human operator]]
    ca_approval[ca_approval: Approve alliance through stakeholder decision or cooperative governance [human reviewer]]
    ca_consultation[ca_consultation: Consult affected and participating parties [stakeholder coordinator]]
    ca_draft[ca_draft: Prepare alliance consultation [coordination proposer]]
    ca_due_diligence[ca_due_diligence: Assess identity, capacity, dependency, capture, and ecological risk [due diligence reviewer]]
    ca_renewal[ca_renewal: Prepare a new alliance term [human reviewer]]
    ca_review[ca_review: Review participation, value, harms, risks, and learning [human reviewer]]
    ca_suspension[ca_suspension: Suspend alliance activity and preserve obligations [human reviewer]]
    ca_terminate_activation((ca_terminate_activation: Terminate before activation completes [human reviewer]))
    ca_terminate_approval((ca_terminate_approval: Terminate after approval review [human reviewer]))
    ca_terminate_consultation((ca_terminate_consultation: Terminate after consultation [human reviewer]))
    ca_terminate_diligence((ca_terminate_diligence: Terminate after due diligence [human reviewer]))
    ca_terminate_draft((ca_terminate_draft: Terminate alliance before consultation [human reviewer]))
    ca_terminate_renewal((ca_terminate_renewal: Terminate after renewal decision [human reviewer]))
    ca_terminate_suspension((ca_terminate_suspension: Terminate from suspension [human reviewer]))
    ca_termination_review((ca_termination_review: Terminate after review [human reviewer]))
    ca_activation -->|participants, commitments, and controls are active / activate -> review| ca_review
    ca_activation -->|activation preconditions fail / terminate -> termination| ca_terminate_activation
    ca_approval -->|approval and separation of duties are complete / approve -> activation| ca_activation
    ca_approval -->|approval requires material redesign / revise -> consultation| ca_consultation
    ca_approval -->|approval is rejected without a viable redesign / terminate -> termination| ca_terminate_approval
    ca_consultation -->|consent, accessibility, and representation are documented / consulted -> due_diligence| ca_due_diligence
    ca_consultation -->|consultation identifies unacceptable harm / terminate -> termination| ca_terminate_consultation
    ca_draft -->|scope and participants are ready / consult -> consultation| ca_consultation
    ca_draft -->|no mandate or unsafe premise / terminate -> termination| ca_terminate_draft
    ca_due_diligence -->|evidence and mitigations are complete / due_diligence_complete -> approval| ca_approval
    ca_due_diligence -->|material gaps require renewed consultation / revise -> consultation| ca_consultation
    ca_due_diligence -->|risk cannot be acceptably mitigated / terminate -> termination| ca_terminate_diligence
    ca_renewal -->|renewal requires fresh consent and scope review / renew -> consultation| ca_consultation
    ca_renewal -->|renewal is declined / terminate -> termination| ca_terminate_renewal
    ca_review -->|review recommends continuation with a new term / renew -> renewal| ca_renewal
    ca_review -->|material risk or unresolved harm requires pause / suspend -> suspension| ca_suspension
    ca_review -->|review recommends closure / terminate -> termination| ca_termination_review
    ca_suspension -->|corrective evidence is complete / resume_review -> review| ca_review
    ca_suspension -->|suspension cannot be safely resolved / terminate -> termination| ca_terminate_suspension
```
