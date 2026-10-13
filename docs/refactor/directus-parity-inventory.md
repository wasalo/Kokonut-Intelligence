# Directus parity inventory

**Review date:** 13 October 2026  
**Status:** source inventory complete; runtime parity remains open.

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

The current Directus permissions are keyed to a single `location_id` on the
Directus user record for the repaired staff filters. The native operator
console uses explicit grants that can authorize a principal for selected
locations. These are different identity models; do not infer a multi-location
equivalence from the presence of a location predicate in both systems.

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
   bulk and relation-expansion queries. Native explicit multi-location grants
   are checked separately from the legacy single-location Directus user field.
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

## Current disposition

Source mapping is complete enough to plan a collection-scoped acceptance suite,
but it does not close the Directus API/field/row/hook parity gate. Directus is
not enabled in the local Kernel candidate, the legacy stack remains stopped,
and no live Directus request was made for this review. Keep Directus optional
and retain its archived state until the retained-use-case inventory and
isolated runtime checks are accepted. The public native location read remains
conservative and is not a substitute for the full Directus role surface.
