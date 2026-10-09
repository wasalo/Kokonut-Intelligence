# Financial Plan Lifecycle

Spec: `budget`

## Invariants

- A plan cannot be activated before it is approved.
- Approval is a human decision; agents cannot approve or close a plan.
- Actuals are derived from verified expense_event and revenue_event rows.
- Closing a plan is terminal.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| budget_activate | planner | active | Put plan into effect | cancelled while active | cancel | cancelled | budget_cancel_active | - |
| budget_activate | planner | active | Put plan into effect | period closed | close | closed | budget_close | - |
| budget_approve | human reviewer | approved | Review and approve plan | activate plan | activate | active | budget_activate | human-approval |
| budget_approve | human reviewer | approved | Review and approve plan | cancelled after approval | cancel | cancelled | budget_cancel_approved | human-approval |
| budget_cancel_active | planner | cancelled | Terminal cancelled plan | - | terminal | - | - | terminal |
| budget_cancel_approved | planner | cancelled | Terminal cancelled plan | - | terminal | - | - | terminal |
| budget_cancel_draft | planner | cancelled | Terminal cancelled plan | - | terminal | - | - | terminal |
| budget_close | planner | closed | Terminal closed plan | - | terminal | - | - | terminal |
| budget_draft | planner | draft | Create financial plan | approved by reviewer | approve | approved | budget_approve | entry |
| budget_draft | planner | draft | Create financial plan | cancelled before approval | cancel | cancelled | budget_cancel_draft | entry |

## Sources

- `schemas/postgres/176_financial_planning.sql`
- `services/planning/budget.py`

## Governance Controls

- Human approval is required before activation or closure.
- Agents cannot approve or close budgets.

## Data and Persistence

- budget | budget_line, expense_event, revenue_event

## Audit Controls

- Lifecycle transitions are recorded with actor and timestamp.
- Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.

## Tests

- `tests/test_planning_budget.py`
- `tests/test_sandop.py`

## Mermaid

```mermaid
flowchart TD
    budget_activate[budget_activate: Put plan into effect [planner]]
    budget_approve[budget_approve: Review and approve plan [human reviewer]]
    budget_cancel_active((budget_cancel_active: Terminal cancelled plan [planner]))
    budget_cancel_approved((budget_cancel_approved: Terminal cancelled plan [planner]))
    budget_cancel_draft((budget_cancel_draft: Terminal cancelled plan [planner]))
    budget_close((budget_close: Terminal closed plan [planner]))
    budget_draft[budget_draft: Create financial plan [planner]]
    budget_activate -->|cancelled while active / cancel -> cancelled| budget_cancel_active
    budget_activate -->|period closed / close -> closed| budget_close
    budget_approve -->|activate plan / activate -> active| budget_activate
    budget_approve -->|cancelled after approval / cancel -> cancelled| budget_cancel_approved
    budget_draft -->|approved by reviewer / approve -> approved| budget_approve
    budget_draft -->|cancelled before approval / cancel -> cancelled| budget_cancel_draft
```
