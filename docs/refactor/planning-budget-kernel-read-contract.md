# Planning budget Kernel read contract

CAP-031's first native Kernel slice is a bounded location budget summary at
`GET /operator/api/planning/{location_id}/budgets`. It requires an authenticated
operator, an active `planning_budget:read` grant for the location, and signed
transaction-bound tenant context. PostgreSQL rechecks the context and grant.

Only plans owned by the location's current organization and containing budget
lines explicitly assigned to that exact location are included. Organization
budget lines with a null location are not apportioned to farms. The response
contains plan lifecycle, currency and period, whether an objective is linked,
location budget-line count/total, verified in-period expense totals in the plan
currency, the corresponding planned-minus-expense variance, foreign-currency
expense count, and scenario count. Expense amounts in other currencies are
counted separately and excluded from variance; no conversion rate is assumed.

Plan labels, objective identity, budget categories, line notes, scenario names
and assumptions, expense descriptions/vendors/evidence, and individual
transaction identifiers are omitted. A dedicated non-login database role
owns the security-definer projection. Runtime receives function execution but
no new direct reads; Directus receives no new grant and cannot execute the
projection.

This is a read foundation, not CAP-031 parity. Plan creation and governed
approval/activation/closure, budget-line edits, revenue and cash-flow
reconciliation, objectives/KPIs, portfolio allocation, production/capacity
S&OP, multi-currency conversion, populated fixture comparison, live
OIDC/browser behavior, universal ACL/RLS, and MAN-CAP-031 owner acceptance
remain open.

Migration 455 is tested only on disposable PostgreSQL 16 by
`scripts/check-planning-budget-summary-disposable.py`; it is not applied to the
candidate or legacy database.
