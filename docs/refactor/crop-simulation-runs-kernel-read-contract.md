# Crop-simulation run and state Kernel read contract

## Scope

The CAP-002 slice exposes a private OIDC Gateway read:

```text
GET /operator/api/crop-simulations/{location_id}/runs?limit=25&offset=0
GET /operator/api/crop-simulations/{location_id}/runs/{run_id}?limit=25&offset=0
```

It returns a bounded page of completed runs belonging to `crop_simulation`
twins whose status is active or archived. Each row includes the twin/run IDs
and name, run timing, final yield and unit, total water, total nitrogen, and
average soil carbon. A detail route also returns one completed run's allowlisted
summary and a bounded page of its persisted daily states. State output covers
soil, crop, water, weather, and carbon measurements. Both routes read persisted
results; they do not create a twin, run a simulation, or expose a what-if
scenario.

## Authorization and data access

- Both routes require the exact `digital_twin:read` grant for the requested
  location. Other methods, suffixes, and unrecognized paths remain protected.
- Operator/location/run UUIDs and pagination are validated before connecting.
- A repeatable-read, read-only transaction installs signed tenant context before
  the count, run, and state queries, keeping all reads on one snapshot.
- Every query filters the exact location, `crop_simulation` twin type, active or
  archived twin lifecycle, and completed simulation status. Detail state rows
  are joined through that same authorized run and location.
- Page size is capped at 50; statement and lock timeouts are bounded. The
  connection is rolled back and closed on success and failure.
- Raw run parameters, arbitrary metadata, error messages, cost/revenue/margin,
  and configuration are not returned. Daily state IDs and metadata are omitted.
- Responses use `Cache-Control: no-store` and `Vary: Cookie`.
- No migration or additional runtime dependency is required.

## Simulation repeatability boundary

The legacy daily weather variation now uses process-independent SHA-256
jitter keyed by an integer `weather_seed`; the default is `0`. The selected
seed is recorded in each run's parameter overrides and included in the
simulation command result. This replaces Python's process-salted `hash()`
behavior, which made identical inputs vary between interpreter processes.
The synthetic fixture in `tests/fixtures/crop_simulation_reference_v1.json`
pins two 30-day seed cases. It is a regression oracle for the current model
implementation, not a reference from populated legacy farm data or evidence of
agronomic correctness. The private Gateway projection continues to omit raw
parameters.

## Verification boundary

Focused tests cover exact route policy, pre-connection validation, signed
context ordering, read-only transaction controls, location/type/lifecycle
filters, bounded run/state paging, output allowlisting, cleanup, authenticated
HTTP behavior, and missing-grant denial. Existing digital-twin unit tests
continue to pass.

The regression fixture establishes repeatability only for its synthetic inputs.
These checks do not establish agronomic correctness or populated legacy output
parity, validate live OIDC or browser behavior, establish RLS/least-privilege
grants, or close MAN-CAP-002.

## Operator console

The console shows run summaries and persisted daily states only for a signed
session with the exact `digital_twin:read` grant for a syntactically valid
location. Same-origin/no-store requests use pages of at most 25 rows and check
the response location, page offset, and selected run ID. Stale list or detail
responses are discarded after a location or run change. Fixed run and state
fields render through text nodes. Run/state IDs remain internal to requests;
raw parameters, errors, metadata, and financial values are not displayed. The
panel never starts or modifies a simulation. These source and DOM checks are
not live browser or populated-model acceptance ([evidence](builds/2026-10-23-recovery/cap-002-crop-simulation-console.json)).

## Rollback

To roll back only the console, remove its panel, exact-scope bootstrap, event
bindings, and focused contract test; the existing read-only Gateway endpoints
remain available. To roll back the full Kernel read slice as well, remove both
routes and their exact `digital_twin:read` policy entries. Neither path needs a
schema or data rollback; existing CLI simulation behavior is unchanged.
