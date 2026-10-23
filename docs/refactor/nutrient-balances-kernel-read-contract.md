# Nutrient balance summaries Kernel read contract

## Scope

The CAP-002 slice exposes a private OIDC Gateway read:

```text
GET /operator/api/nutrients/{location_id}/balances?limit=25&offset=0
```

It returns a bounded grouping by season and crop with budget count, area, and
nitrogen, phosphorus, and potassium input/removal/surplus totals. The source is
`v_nutrient_balance`, which selects the latest verified/published budget per
plot and season. This endpoint is an advisory summary; it does not recommend or
apply inputs.

## Authorization and data access

- The route requires the exact `nutrient_budget:read` grant for the requested
  location. Other methods, suffixes, and unrecognized paths remain protected.
- Operator/location UUIDs and pagination are validated before connecting.
- A repeatable-read, read-only transaction installs signed tenant context before
  count and page queries, keeping both reads on one snapshot.
- Both queries filter by the requested location. The canonical view excludes
  draft, submitted, and rejected budgets and returns only the latest verified
  or published budget for each plot and season.
- Page size is capped at 50; statement and lock timeouts are bounded. The
  connection is rolled back and closed on success and failure.
- The projection omits plot/budget IDs, product-level input details, free-text
  notes, soil-test records, and financial costs.
- Responses use `Cache-Control: no-store` and `Vary: Cookie`.
- No migration or additional runtime dependency is required.

## Verification boundary

Focused tests cover exact route policy, pre-connection validation, signed
context ordering, read-only transaction controls, location filtering, grouped
N/P/K output, bounded pagination, omitted fields, cleanup, authenticated HTTP
behavior, and missing-grant denial. Existing nutrient-budget unit tests pass.

These checks do not establish populated-data parity, all nutrient input and
soil-test display needs, independent soil-science review, live OIDC/browser
behavior, database RLS/least-privilege boundaries, or MAN-CAP-002 acceptance.

## Rollback

This additive read route can be rolled back by removing its route registration
and exact `nutrient_budget:read` policy entry. No schema or data rollback is
required; existing nutrient-budget CLI behavior remains unchanged.
