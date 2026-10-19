# Threatcasting Kernel read contract

The Kernel operator API exposes only a bounded, location-scoped read projection
of stored backcast plans:

- `GET /operator/api/threatcasting/{location_id}/backcast-plans`
- `GET /operator/api/threatcasting/{location_id}/backcast-plans/{plan_id}`

Both routes require an authenticated OIDC operator with the exact
`threatcasting:read` grant for the requested location. The service sets signed
tenant context on the same read-only PostgreSQL transaction before querying,
uses location-qualified joins and selectors, applies statement/lock timeouts,
and closes the transaction without committing. Responses use `Cache-Control:
no-store` and `Vary: Cookie`.

The list route is keyset paginated and capped at 100 plans. Detail is capped at
500 milestones and returns only the plan header, narrative title/type, threat
name, milestone state, dependency IDs, and entered completion evidence. It does
not include arbitrary metadata, full narrative stories, or feedback payloads.
Every response includes `advisory_only: true`. These routes cannot create or
edit plans, change milestone state, publish a recommendation, or execute an
intervention. Existing source and database checks continue to reject cyclic or
cross-plan milestone dependencies.

This is a code-level Kernel read path, not a claim of universal tenant
isolation. The legacy application database identity still has broad access,
domain-table RLS and least-privilege runtime ACLs are not established for these
tables, and live OIDC/browser, populated output/evidence parity, and named
MAN-CAP-026 owner acceptance remain open. Do not mark CAP-026 accepted until
those gates have evidence.

## Rollback

Revert the route registration, policy, service, and tests together if the read
surface must be withdrawn. No schema migration or data mutation is required;
there is no database rollback step.
