# Management work Kernel read contract

CAP-030's first native Kernel slice is a location workload summary at
`GET /operator/api/management/{location_id}/summary`. It requires an
authenticated operator, an active `management_workflow:read` grant for the
location, and signed transaction-bound tenant context. PostgreSQL independently
rechecks the grant and context.

The response contains work item totals by lifecycle state, open high/critical
priority counts, due-date and SLA breach totals, proposed/accepted claim
counts, open/resolved escalation counts, and latest work-event time. Only
records whose `work_item.location_id` exactly matches the requested location
are included. Work items without a location and organization-only records are
not inferred into a farm scope.

The response omits task titles/descriptions, assignee and actor identities,
claimant identity, estimated effort, skill requirements, event notes, and
escalation reasons. A dedicated non-login database role owns the
security-definer summary function; runtime receives function execution, while
Directus receives neither function execution nor new grants.

This is an aggregate read foundation, not CAP-030 parity. Assignment, work
selection, lifecycle transition, SLA policy configuration, escalation creation
and resolution, and audit-history detail remain in the existing services and
require their own Kernel contracts and acceptance. Existing records without a
location need data review before they can appear in a location-scoped view.

Migration 454 is tested only on disposable PostgreSQL 16 by
`scripts/check-management-work-summary-disposable.py`; the candidate and legacy
databases require a separate rollout gate.
