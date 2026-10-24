# Nutrient operations console contract

## Scope

The private operator console presents four read-only views for one granted
location:

```text
GET /operator/api/nutrients/{location_id}/balances?limit=25&offset=0
GET /operator/api/nutrients/{location_id}/soil-tests?limit=25&offset=0
GET /operator/api/nutrients/{location_id}/events/inputs?limit=25&offset=0
GET /operator/api/nutrients/{location_id}/events/removals?limit=25&offset=0
```

The balances view groups verified/published nutrient balances by season and
crop. Soil tests include recorded or verified measurements and advisory
recommendations. Input and harvest-removal events preserve event and parent
budget lifecycle status separately. The console is read-only; it does not
create or verify budgets, tests, or events.

## Authorization, paging, and privacy

- The panel is hidden unless the signed OIDC session has the exact
  `nutrient_budget:read` grant for a syntactically valid location. The Gateway
  independently establishes signed tenant context for each route.
- A fixed local view map selects only the four registered routes. The UI pages
  25 records at a time, checks location, offset, and event type, and discards
  stale responses after a location or view change. Requests use same-origin
  credentials and `no-store` caching.
- Rows display fixed allowlisted scalar fields through text nodes. Soil-test,
  event, and plot identifiers; notes; and arbitrary metadata are not rendered.
- Input costs appear only as an amount plus a classified currency code. An
  unclassified historic amount is withheld. The UI never converts or combines
  values across currencies.
- No migration, database write, provider, or additional dependency is needed.

## Verification boundary

The focused source, Gateway, domain, and registered-route checks cover view
allowlists, exact route scope, response correlation, bounded paging, currency
handling, text-only rendering, and inline JavaScript syntax. They do not prove
populated legacy parity, live OIDC/browser acceptance, RLS/least-privilege
grants, historic currency reconciliation, or MAN-CAP-002 acceptance
([evidence](builds/2026-10-23-recovery/cap-002-nutrient-console.json)).

## Rollback

Remove the additive console panel, its scope-driven bootstrap and event
listeners, and its focused console contract test. Existing read-only Gateway
routes, schema, and legacy nutrient operations remain unchanged; no migration
or data rollback is needed.
