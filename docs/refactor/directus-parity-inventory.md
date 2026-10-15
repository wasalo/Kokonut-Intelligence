# Directus parity inventory

**Review date:** 13 October 2026  
**Status:** source inventory complete; isolated runtime probe completed with a
fail-closed result; runtime parity remains open.

## Decision boundary

Directus is an optional administrative and compatibility adapter. Its current
database role has bounded DML access, but that does not make its API permissions,
field allowlists, row filters, or hooks equivalent to the native Gateway. The
native implementation should replace a Directus use case only after that
specific use case has a named contract and accepted parity evidence. This
inventory is not evidence that the whole Directus surface has been replaced.

## Source surface reviewed

| Surface | Current source | What the source establishes | What remains unverified |
| --- | --- | --- | --- |
| API roles and CRUD rules | [`config/directus/permissions.sql`](../../config/directus/permissions.sql) | Staff policies define collection actions, writable fields, row filters, and create validation. The SQL includes manager, supervisor, finance, analyst, auditor, and field-worker policy identities, plus separate agent read/write/full policy tiers. A repair adds location filters to selected staff reads and creates. | Effective permissions after seed/bootstrap, policy composition, actual caller identity, and cross-location allow/deny behavior in the pinned running Directus image. |
| Database identity | [`optional-database-roles.md`](optional-database-roles.md) | The Directus service can bootstrap with an owner-backed one-shot operation and run under a non-owner DML role. The runtime role is separate from the native API and analytics roles. | Directus API enforcement under that runtime identity; the role alone does not enforce collection, field, or tenant policy. |
| Lifecycle and accountability hooks | [`extensions/kokonut-hooks/src/workflow.ts`](../../extensions/kokonut-hooks/src/workflow.ts), [`index.ts`](../../extensions/kokonut-hooks/src/index.ts), [`roles.ts`](../../extensions/kokonut-hooks/src/roles.ts) | Thirty-five collections use the shared lifecycle transition map. Hook code resolves role slugs from server accountability, validates selected payloads and tenant references, records transitions, applies domain calculations, and defines two scheduled jobs. | Hook-by-hook parity against native service paths, execution/retry behavior under the deployed Directus image, and authenticated before/after database evidence. |
| Tenant and Field Collector gates | Permission SQL plus [`tests/test_directus_tenant_permissions.py`](../../tests/test_directus_tenant_permissions.py) | The seed repair uses `$CURRENT_USER.location_id`; Field Collector-origin farm-activity reads are excluded because the Directus permission DSL cannot express its cross-table source, revision, and consent rules. The source tests only assert that the SQL contains the expected repair. | Effective multi-location grants, row visibility, write denials, and that every Field Collector route remains on the Gateway path in a live Directus request. |
| Schema metadata | [`tests/test_directus_metadata.py`](../../tests/test_directus_metadata.py) and [`schemas/directus/snapshots/schema_latest.json`](../../schemas/directus/snapshots/schema_latest.json) | The checker compares snapshot sort fields and physical field metadata, and can query the local Compose database when it is running. | Permission parity, API response shape, current runtime identity, or whether the optional Directus profile is deployed. |
| Native replacement surface | [`services/gateway/router.py`](../../services/gateway/router.py), [`services/gateway/operator_auth.py`](../../services/gateway/operator_auth.py), [`native-location-reads.md`](native-location-reads.md), and the [operator console contract](kernel-operations-console.md) | Native routes cover a deliberately bounded public read surface and selected authenticated reviewer, farm-activity, and Field Collector operations. Their policies are explicit and unknown routes remain protected. | Generic CRUD, all Directus collections and fields, admin UI behavior, and one-to-one role semantics are not implemented as native parity. |

The repaired staff permission filters reference
`$CURRENT_USER.location_id`, but the restored populated archive's
`directus_users` table has no `location_id` column. A pinned-image probe showed
the synthetic Field Worker requests denied, with no synthetic rows visible;
that is fail-closed behavior, not proof of correct own-location access or
cross-location isolation. The owner selected organization/location grants as
the Directus tenant model. The native operator console already uses those
explicit grants. Directus still needs a supported mapping from its
authenticated user to Kokonut's `operator_identity`, plus effective
permission filters that evaluate the same active operator, organization,
location, resource, and action grants. Do not infer equivalence from a legacy
`$CURRENT_USER.location_id` predicate.

The SQL also grants `fields = '*'` on many read rules, so a row predicate does
not establish field privacy. The Auditor policy deliberately has unfiltered
reads for collections beyond the ten-collection staff location-repair list,
including reporting and governance records. Confirm that this global forensic
scope is intended before replacing it with tenant-scoped native routes; do not
silently narrow it or call it equivalent to the native operator grants.

The hook source also has effects beyond request validation: NOI snapshot
recalculation, financial projection writes, lifecycle history, and daily/weekly
scheduled callbacks. The daily NOI callback calls the snapshot upsert path. The
weekly callback currently performs a grouped read of verified, source-eligible
farm activity and logs the number of locations; it does not persist snapshot
rows. Decide whether that callback is an unfinished placeholder or an intended
capability before claiming scheduled-output parity. These paths need separate
owned-job and projection decisions before disabling hooks or Directus.

## Scoped parity procedure

Use this inventory as the input to a future isolated Directus acceptance run.
For each retained use case, record the collection, action, role/policy, allowed
fields, row predicate, lifecycle transition, hook effects, and native route or
explicitly optional owner. Then use disposable identities and rows to verify:

1. The pinned image has completed its owner-backed bootstrap and is healthy
   under `kokonut_directus_runtime`.
2. Anonymous, staff, reviewer, analyst, auditor, and agent identities receive
   the expected collection and field access; rejected fields are not echoed.
3. A principal scoped to location A cannot read or mutate location B, including
   bulk and relation-expansion queries. Verify Directus resolves the principal
   to the same active organization/location grants as the Gateway, including
   shared locations only when an active share and operator grant both exist.
4. Lifecycle writes exercise allowed and denied transitions, independent
   reviewer attribution, append-only history, and domain hook effects.
5. Field Collector-origin rows are hidden from legacy Directus reads, while
   native collection review/use routes preserve consent, revision, and grant
   checks.
6. Scheduled NOI and weekly snapshot work has one active owner, an idempotency
   and recovery policy, and output parity before any Directus schedule is
   disabled.

Keep credentials private and use only a disposable populated clone. Capture
aggregate results and sanitized request/response evidence; remove synthetic
users, rows, sessions, and permissions after the run. Do not start a second
schedule owner during the comparison.

## Isolated runtime result — 13 October 2026

The pinned Directus 12.1.1 image bootstrapped successfully against a fresh
internal-only clone of the populated archive and became healthy. Admin login
returned HTTP 200, while anonymous `farm_activity` collection access was
denied. The copied database completed its ordered migration replay with zero
pending migrations. The optional consumer-role fixture passed for the
separate Directus DML role.

The cloned `directus_users` table did not contain `location_id`, although the
Field Worker `farm_activity` read/update and related staff filters use
`$CURRENT_USER.location_id`. Two synthetic locations and rows were available.
Both synthetic Field Worker reads returned HTTP 403 and exposed zero synthetic
rows. Because the role was denied even its own row and the identity had no
location attribute to evaluate, this is a fail-closed result only; it does not
validate scoped read/write behavior, field privacy, or parity. Later identity
creation retries hit Directus `LIMIT_EXCEEDED`, so no second complete run was
possible. The probe did not start the hooks extension or scheduled jobs.

The disposable API fixture's cleanup path did not complete through Directus
for the first synthetic identities. The entire isolated recovery project,
including its database volume, Directus runtime, and private network, was then
removed; no synthetic identities or rows remain in the candidate or archived
source. The candidate stack remained healthy and the legacy stack remained
stopped. Sanitized results are retained in
[`directus-api-parity.json`](builds/2026-10-13-recovery/directus-api-parity.json).

## Current disposition

The runtime probe narrows the next Directus task: bind the Directus principal
to the Kokonut operator identity and implement the owner-selected
organization/location grant model in effective permissions, then rerun
own-location, cross-location, write, and field-visibility requests. Hook-by-hook and
scheduled-job parity still need separate checks. Keep Directus optional and
retain its archived state until each retained use case has accepted evidence.
The public native location read remains conservative and is not a substitute
for the full Directus role surface.

## Parity fixture preflight guard — 14 October 2026

The acceptance script previously discovered the missing
`directus_users.location_id` after creating temporary Field Worker identities
and farm-activity rows. It now stops as soon as the database schema check finds
that required field missing, before those API/database writes. Three source
checks plus a fake-schema execution pass; the execution confirms the blocked
result without synthetic write requests. It does not claim any runtime
permission result. The owner has since selected organization/location grants,
so the next fixture must bind a Directus user to an existing Kokonut operator
identity and verify the same active grants; a synthetic `location_id` user
field is no longer the target contract ([evidence](builds/2026-10-14-recovery/directus-schema-preflight-guard.json)).
