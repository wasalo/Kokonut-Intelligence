# Nutrient input and removal Kernel read contract

## Scope

CAP-002 exposes two private, paginated Gateway reads:

```text
GET /operator/api/nutrients/{location_id}/events/inputs?limit=25&offset=0
GET /operator/api/nutrients/{location_id}/events/removals?limit=25&offset=0
```

The input read returns product/type, application rate, N/P/K quantities, and
currency-qualified cost state.
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
  requested location. Budget IDs, notes, arbitrary metadata, and the removal
  factor's free-text source are omitted.
- Migration 601 adds optional per-input `cost_currency_code` without assigning
  a default. New or changed cost amounts require a three-letter uppercase code;
  historic amounts remain unclassified unless an operator explicitly
  reconciles them. No location-wide currency is assumed and no conversion is
  performed.
- An input with a classified cost returns `cost: {amount, currency_code}` and
  `cost_status: "classified"`. An input with no cost returns null and
  `not_recorded`. A historic cost whose currency is unknown returns a null
  amount and `currency_unclassified`; the raw amount is not exposed. Nutrient
  summaries group cost amounts by currency and report the count of unclassified
  costs separately rather than summing them.
- Responses use `Cache-Control: no-store` and `Vary: Cookie`.
- No external provider is required. Migration 601 is required before deploying
  the currency-aware Gateway and nutrient-budget writer.

## Verification boundary

Focused tests cover exact policies, both event types, pre-connection rejection,
same-transaction signed context, parent-location and child-status filters,
distinct parent/event lifecycle, deterministic bounded pagination, tenant-safe
plot IDs, omitted fields, connection cleanup, no-store responses, and denial
before data access when the grant is missing.

These checks establish the currency capture and aggregation contract only; they
do not reconcile historic unclassified amounts, establish populated-data
parity, validate live ZITADEL/browser behavior, prove database RLS or
least-privilege boundaries, or close MAN-CAP-002.

## Rollback

The migration is ordered and immutable. The prior application can still read
the view's existing columns, but its cost writer cannot create or change a cost
without a currency and will fail closed. If rolling back application code,
disable legacy cost writes until the currency-aware writer is restored. Keep the
column and recorded codes; do not restore an aggregate that sums mixed or
unclassified currencies. A later forward migration is required for any schema
reversal; never edit migration 601 after application.
