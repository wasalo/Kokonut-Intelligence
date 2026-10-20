# Business planning Kernel draft-create contract

This contract defines the first location-scoped Kernel write for stored
business-model canvases. It is additive: legacy CLI and optional Directus table
permissions are not changed by migration 463 while their remaining workflows
are being migrated.

## Route and authorization

`POST /operator/api/business-planning/{location_id}/canvases` and
`POST /operator/api/business-planning/{location_id}/canvases/from-data` require
an authenticated OIDC operator, CSRF validation, and the exact active
`business_planning:create` grant for the requested location. The Gateway binds
the current session proof to a signed tenant context in the same transaction as
the database function call. PostgreSQL repeats the location, actor, tenant, and
grant checks; browser-supplied organization IDs are not accepted. The
`from-data` suffix is POST-only; reads and other methods remain protected.

## Request and lifecycle

The caller supplies a stable UUID `request_id`, a canvas name, optional
description/fiscal year/tags, and up to 64 KiB of the nine canonical BMC blocks.
Unknown fields, invalid block shapes, duplicate tags, non-finite JSON numbers,
NUL characters, excessive nesting, and oversized content fail before a database
connection or before the function writes.

Creation always produces a location-owned `draft` with version 1. The base
route accepts caller-composed blocks. The `from-data` route accepts the same
request ID and metadata fields but rejects caller-supplied blocks, reads the
location-bound suggestion sources after signed context is established, and
creates the result in that same transaction. It returns source categories and
populated block names and stores bounded `suggested-from:<source>` canvas tags
alongside `auto-generated`; these categories are not row-level evidence links.
Generated mode reserves capacity for at most 20 source categories and permits
at most 10 base tags including `auto-generated`. Neither
route verifies, submits, publishes, attests, or modifies an existing canvas.

Repeating the same request ID and normalized payload returns the original
canvas. Reusing the request ID for changed content returns a conflict. For
generated drafts, the normalized suggestion output participates in that
fingerprint; if source records change between a retry and the original request,
the request is rejected as changed content instead of silently creating a
second canvas. The private append-only request ledger records the operator,
location, request, canvas, and SHA-256 payload fingerprint.

## Compatibility and remaining boundary

Migration 463 grants the Gateway a non-login, column-scoped creator role through
one bounded `SECURITY DEFINER` function. Runtime can execute that function;
Directus cannot. The migration intentionally does not revoke existing direct
canvas DML from CLI or Directus roles. This keeps legacy create/edit workflows
working while their authenticated replacements are built. It also means this
slice does not establish universal canvas write isolation or RLS.

The shared one-click suggestion builder uses current schema fields and
location-bound records, filters to verified/published business data, groups
expenses by native currency, and includes feedback only when it is public,
consented, and has at least five identified respondents. Focused tests cover
its source-selection rules and that the Gateway establishes signed context
before suggestion reads. The Gateway now has a generated-draft path, but this
does not prove populated-output parity. The fourteen-section status report now
has a separate location-scoped read route under
`comprehensive_status:read`; its read contract is documented separately, and
populated-output parity remains open. A location-scoped, draft-only block-edit
route and version-history read now cover the nine canvas blocks, but not
metadata edits or lifecycle transitions. Existing CLI/Directus direct writers
remain compatible and can still bypass Kernel version history, so universal
write isolation remains open ([edit contract](business-planning-kernel-edit-contract.md)).

## Verification boundary

Focused source/route tests cover signed-context call ordering before generated
source reads, payload limits, transaction rollback/cleanup, CSRF route policy,
response status, and denial mapping. The disposable PostgreSQL 16 check applies/replays migrations 457 and
463 and verifies owner-grant creation, idempotent retry, changed-payload
collision, malformed blocks, cross-location and missing-grant denial, ledger
immutability, function ACLs, and unchanged legacy direct-DML behavior. The
candidate and legacy databases are not touched. Migration 463 is not rolled
out.
