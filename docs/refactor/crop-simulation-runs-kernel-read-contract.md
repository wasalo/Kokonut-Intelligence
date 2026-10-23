# Crop-simulation run summaries Kernel read contract

## Scope

The CAP-002 slice exposes a private OIDC Gateway read:

```text
GET /operator/api/crop-simulations/{location_id}/runs?limit=25&offset=0
```

It returns a bounded page of completed runs belonging to `crop_simulation`
twins whose status is active or archived. Each row includes the twin/run IDs
and name, run timing, final yield and unit, total water, total nitrogen, and
average soil carbon. The route reads persisted results; it does not create a
twin, run a simulation, reveal daily state, or expose a what-if scenario.

## Authorization and data access

- The route requires the exact `digital_twin:read` grant for the requested
  location. Other methods, suffixes, and unrecognized paths remain protected.
- Operator/location UUIDs and pagination are validated before connecting.
- A repeatable-read, read-only transaction installs signed tenant context before
  the count and result queries, keeping count and page on one snapshot.
- Both queries filter the exact location, `crop_simulation` twin type, active or
  archived twin lifecycle, and completed simulation status.
- Page size is capped at 50; statement and lock timeouts are bounded. The
  connection is rolled back and closed on success and failure.
- Raw run parameters, arbitrary metadata, error messages, cost/revenue/margin,
  configuration, and simulation-state records are not returned.
- Responses use `Cache-Control: no-store` and `Vary: Cookie`.
- No migration or additional runtime dependency is required.

## Verification boundary

Focused tests cover route policy, pre-connection validation, signed context
ordering, read-only transaction controls, location/type/lifecycle filters,
bounded paging, output allowlisting, cleanup, authenticated HTTP behavior, and
missing-grant denial. Existing digital-twin unit tests continue to pass.

These checks do not run the model, establish deterministic simulation output,
prove populated legacy parity, expose daily state/detail, validate live OIDC or
browser behavior, establish RLS/least-privilege grants, or close MAN-CAP-002.

## Rollback

This additive read route can be rolled back by removing its route registration
and exact `digital_twin:read` policy entry. No schema or data rollback is
required; existing CLI simulation behavior is unchanged.
