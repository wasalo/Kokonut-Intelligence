# Nutrient input and removal Kernel read contract

## Scope

CAP-002 exposes two private, paginated Gateway reads:

```text
GET /operator/api/nutrients/{location_id}/events/inputs?limit=25&offset=0
GET /operator/api/nutrients/{location_id}/events/removals?limit=25&offset=0
```

The input read returns product/type, application rate, and N/P/K quantities.
The removal read returns harvest date, crop, yield, unit, and N/P/K quantities.
Both preserve the child event and parent budget lifecycle statuses so a
verified child under a draft budget cannot be mistaken for a published balance.
These reads do not change or approve any record.

## Authorization and data access

- Each route requires the exact `nutrient_budget:read` grant for the requested
  location. Only GET on the exact `inputs` or `removals` route is matched.
- Operator/location UUIDs, event type, and pagination are validated before
  connecting.
- One repeatable-read, read-only transaction installs signed tenant context
  before the count and page reads. Both queries join each child through its
  parent budget and filter the parent `location_id` plus the legacy-visible
  child states `recorded` and `verified`.
- Parent budget status is reported but not filtered, matching the legacy
  dashboard's child-status behavior without concealing parent lifecycle.
- Page size is capped at 50, offset at 10,000, statement timeout at five seconds,
  and lock timeout at two seconds. Connections roll back and close on all exits.
- Plot IDs are returned only when the referenced plot's farm belongs to the
  requested location. Budget IDs, costs, notes, arbitrary metadata, and the
  removal factor's free-text source are omitted.
- `nutrient_input.cost` has no currency field or documented location-currency
  binding, so cost is withheld until its unit is defined. Legacy cost-summary
  parity remains open.
- Responses use `Cache-Control: no-store` and `Vary: Cookie`.
- No migration or additional provider is required.

## Verification boundary

Focused tests cover exact policies, both event types, pre-connection rejection,
same-transaction signed context, parent-location and child-status filters,
distinct parent/event lifecycle, deterministic bounded pagination, tenant-safe
plot IDs, omitted fields, connection cleanup, no-store responses, and denial
before data access when the grant is missing.

These checks do not establish populated-data parity, cost/currency semantics,
live ZITADEL/browser behavior, database RLS or least-privilege boundaries, or
MAN-CAP-002 acceptance.

## Rollback

Remove the additive event route, exact authorization policy, service module,
tests, and documentation. No schema or data rollback is required; existing
nutrient-budget commands and reads remain unchanged.
