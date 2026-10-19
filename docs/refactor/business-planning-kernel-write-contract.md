# Business planning Kernel draft-create contract

This contract defines the first location-scoped Kernel write for stored
business-model canvases. It is additive: legacy CLI and optional Directus table
permissions are not changed by migration 463 while their remaining workflows
are being migrated.

## Route and authorization

`POST /operator/api/business-planning/{location_id}/canvases` requires an
authenticated OIDC operator, CSRF validation, and the exact active
`business_planning:create` grant for the requested location. The Gateway binds
the current session proof to a signed tenant context in the same transaction as
the database function call. PostgreSQL repeats the location, actor, tenant, and
grant checks; browser-supplied organization IDs are not accepted.

## Request and lifecycle

The caller supplies a stable UUID `request_id`, a canvas name, optional
description/fiscal year/tags, and up to 64 KiB of the nine canonical BMC blocks.
Unknown fields, invalid block shapes, duplicate tags, non-finite JSON numbers,
NUL characters, excessive nesting, and oversized content fail before a database
connection or before the function writes.

Creation always produces a location-owned `draft` with version 1. It does not
compute suggestions, verify, submit, publish, attest, or modify an existing
canvas. Repeating the same request ID and normalized payload returns the
original canvas. Reusing the request ID for changed content returns a conflict.
The private append-only request ledger records the operator, location, request,
canvas, and SHA-256 payload fingerprint.

## Compatibility and remaining boundary

Migration 463 grants the Gateway a non-login, column-scoped creator role through
one bounded `SECURITY DEFINER` function. Runtime can execute that function;
Directus cannot. The migration intentionally does not revoke existing direct
canvas DML from CLI or Directus roles. This keeps legacy create/edit workflows
working while their authenticated replacements are built. It also means this
slice does not establish universal canvas write isolation or RLS.

The legacy one-click suggestion pipeline and thirteen-section status report
remain separate. This route accepts a caller-composed draft; it is not a parity
claim for generated suggestions, aggregate status, existing canvas edits, or
version history.

## Verification boundary

Focused source/route tests cover signed-context call ordering, payload limits,
transaction rollback/cleanup, CSRF route policy, response status, and denial
mapping. The disposable PostgreSQL 16 check applies/replays migrations 457 and
463 and verifies owner-grant creation, idempotent retry, changed-payload
collision, malformed blocks, cross-location and missing-grant denial, ledger
immutability, function ACLs, and unchanged legacy direct-DML behavior. The
candidate and legacy databases are not touched. Migration 463 is not rolled
out.
