# Directus parity inventory

**Review date:** 25 October 2026
**Status:** source inventory, the fail-closed tenant authorization adapter,
and an organization/location permission seed repair are implemented. Pinned
Directus 12.1.1 acceptance confirms grant-scoped Field Note reads, but the
unlicensed API hides the Field Worker's custom `farm_activity` permission rows;
the owner selected Gateway operations with Directus optional. The curated
permission seed now removes `farm_activity` access from its nine managed role
policies, including stale rows from earlier seed versions, so a future license
change cannot silently restore a parallel operations API. A fresh pinned
Directus 12.1.1 profile accepted and replayed that seed under
`kokonut_directus_runtime`; it reported zero managed `farm_activity` rules and
retained 14 other role permissions ([runtime evidence](builds/2026-10-15-recovery/directus-profile-disposable.json)).
Gateway role
templates cover the native Field Collector workflow, and a separate native API
now provides scoped operations for non-Field-Collector farm-activity records.
Migration 404 and its disposable PostgreSQL acceptance establish this bounded
Gateway slice only; broader collection, field/relationship, hook, and schedule
parity remain open.

Scoped Directus create and update filters validate known references against tenant location. Plot location is resolved through `plot.farm_id` to `farm.location_id` because the plot table has no location column; writable `stakeholder_feedback.farm_id` references use the same farm location. `labor_event.staff_id` and `metric_proposal.reviewed_by` resolve only through direct same-location staff assignment or a `farm_staff_member` edge whose farm belongs to that location. Crop-cycle and harvest references use their direct location columns. For updates, the hook uses authorized target rows and the request database context, and each reference must match every target row. The complete hook suite passes 83 tests, the extension build/type check and 10 Python tenant/compatibility checks pass, and no live Directus run was performed ([evidence](builds/2026-10-25-recovery/directus-reference-location-resolution.json)). Directus `stakeholder_feedback_review` creates now resolve `feedback_id` to the parent location on the request transaction and require the exact child `create` grant there; optional reviewers are location-qualified. Its reads, updates, and deletes remain outside this slice because the managed permission currently grants create only. The writable `mrv_claim.source_record_ids` UUID array remains polymorphic without a source-table discriminator and still needs an explicit source contract. Broader collection, field, relation, hook, schedule, and runtime parity remain open.

The two legacy Directus schedules are now independent explicit opt-ins in the
extension. The legacy root Compose stack keeps both enabled by default for
compatibility; the optional Kernel Directus profile defaults both off. Daily
NOI snapshot reconciliation is separately available through the signed,
default-off Kernel worker, and weekly activity aggregation remains an optional
read-only compatibility effect. No schedule was activated or run by this
change; ownership, runtime identity, overlap, and output parity remain open.

The 23 October runtime probe confirms the pinned unlicensed Directus profile
cannot provide custom permission management: an owner request to create an
`agent_task` rule returns `403 RESOURCE_RESTRICTED` for
`custom_permission_rules_enabled`. `/permissions/me` reports Agent Write as
read-only even though the fresh seed contains its create/update rows. Both the
Agent Write and an ungranted Field Worker create attempts returned 403, and the
synthetic table remained empty. This is useful fail-closed evidence and a
license/configuration prerequisite, not successful role or field parity. Four
focused checks and the pinned disposable profile pass their diagnostic
acceptance; broader Directus parity and CAP-001 remain open
([evidence](builds/2026-10-23-recovery/directus-effective-permissions.json);
[runner](../../scripts/check-directus-profile-disposable.py)).

The disposable API fixture now matches the owner-selected split: farm activity
is denied through Directus even when a synthetic operator has valid tenant
grants, while Field Note reads remain location-scoped. The fixture checks
own/cross-location read denial, write denial without row changes, allowed own
Field Note reads, and hidden cross-location Field Notes. Source checks pass;
this is not a fresh Directus runtime execution and does not close the broader
parity gate ([evidence](builds/2026-10-18-recovery/directus-gateway-only-source-contract.json)).

The hook extension now declares the exact Directus host version pinned by the
base Compose file. A source regression check keeps the package host metadata
aligned with that image. This removes the previous Directus 11 versus 12
compatibility declaration mismatch; it does not establish runtime hook loading
or permission parity.

The curated permission seed now has a repeatable source inventory at
[`builds/2026-10-20-recovery/directus-permission-source-inventory.json`](builds/2026-10-20-recovery/directus-permission-source-inventory.json),
generated and freshness-checked by `scripts/directus_permission_inventory.py`.
It finds 175 literal permission insert declarations: 125 use `fields = '*'`
and 50 name explicit fields. The Auditor policy accounts for 28 wildcard
declarations; Field Worker stakeholder-feedback read is one concrete example.
No `farm_activity` permission insert is present in the seed, consistent with
the Gateway-only decision. The inventory also records four literal
`UPDATE directus_permissions` and one `DELETE` statement, including the managed
`farm_activity` cleanup. It inventories source declarations and mutations only. It does not compute the effective result of conditional inserts, later
updates/deletes, built-in or operator-created policies, or a running Directus
database, and it does not itself authorize narrowing any role's access.

A separate pinned-runtime acceptance now captures the effective rows produced by
the seed in a fresh disposable profile. The nine repository-managed policies
produce 175 rows (125 wildcard-field, 50 explicit-field); no managed
`farm_activity` rows remain, and seed replay preserves the complete normalized
snapshot (SHA-256 `93eec38af045957bb9087c2cfa5549226cb51f3555e1822350c59548989f7877`).
The profile starts healthy and authenticates a synthetic owner under the
dedicated `kokonut_directus_runtime` database identity. This closes the gap
between literal source declarations and effective stored rows for one clean
profile only. The snapshot excludes built-in and operator-created policies and
does not verify API enforcement for each role, populated-target parity, hook
effects, or schedule ownership ([runner](../../scripts/check-directus-profile-disposable.py);
[rows](builds/2026-10-23-recovery/directus-effective-permission-rows.json);
[summary](builds/2026-10-23-recovery/directus-effective-permissions.json)).

The hook register function also now subscribes to the collection-qualified
`<collection>.items.create` and `<collection>.items.update` events documented
by Directus. A Vitest invokes the actual register function and rejects
noncanonical item-event names. This fixes the source event-name mismatch, but
does not prove the pinned server dispatches those listeners or that effective
permissions match Kokonut grants
([evidence](builds/2026-10-15-recovery/directus-hook-event-registration.json)).

The extension layout and artifact were then exercised against a fresh isolated
Directus 12.1.1 database. Directus logged both extensions as loaded; the Field
Collector endpoint returned HTTP 302 to its configured static route; admin
login succeeded; and a synthetic `farm_activity` collection accepted the
schema setup. A malformed `location_id` create was rejected and the collection
remained empty. The hook now throws a typed Directus `INVALID_PAYLOAD` error,
and the request returned HTTP 400. Unit and isolated API checks cover the
status, error code, and absence of an inserted row. This run proves extension
discovery and one actual hook dispatch only; it does not prove
account-to-operator mapping, grants, field privacy, or parity across
collections
([evidence](builds/2026-10-15-recovery/directus-extension-runtime.json)).

## Decision boundary

Directus is an optional administrative and compatibility adapter. Its current
legacy base Compose service still connects as the `kokonut` superuser. A
separate optional Kernel profile now runs the pinned image under
`kokonut_directus_runtime`; role provisioning and owner-backed metadata
bootstrap are separate one-shot operations. Neither a bounded database role nor
the API permissions, field allowlists, row filters, and hooks alone establish
parity with the native Gateway. The native implementation should replace a
Directus use case only after that specific use case has a named contract and
accepted parity evidence. This inventory is not evidence that the whole
Directus surface has been replaced.

## Source surface reviewed

| Surface | Current source | What the source establishes | What remains unverified |
| --- | --- | --- | --- |
| API roles and CRUD rules | [`config/directus/permissions.sql`](../../config/directus/permissions.sql) | Staff policies define other collection actions, writable fields, and business filters. `farm_activity` is intentionally omitted from all nine repository-managed policies; the seed deletes stale managed rows. The Gateway has explicit operator-grant templates for the native Field Collector workflow and a separate `/operator/api/farm-activity-records` contract for non-Field-Collector reads, drafts, and human lifecycle operations. | Fresh pinned-runtime seed apply/replay under `kokonut_directus_runtime` passes and leaves zero managed `farm_activity` rules while retaining other role permissions. Migration 404 is source/disposable-DB verified, not candidate deployed. Historical rows without Gateway audit provenance fail closed for lifecycle transitions. Other collections/fields, field privacy, expanded relations, and retained hook effects remain open. |
| Database identity | [`optional-database-roles.md`](optional-database-roles.md) | The Directus service can bootstrap with an owner-backed one-shot operation and run under a non-owner DML role. The runtime role is separate from the native API and analytics roles. | Directus API enforcement under that runtime identity; the role alone does not enforce collection, field, or tenant policy. |
| Lifecycle and accountability hooks | [`extensions/kokonut-hooks/src/workflow.ts`](../../extensions/kokonut-hooks/src/workflow.ts), [`index.ts`](../../extensions/kokonut-hooks/src/index.ts), [`roles.ts`](../../extensions/kokonut-hooks/src/roles.ts) | Thirty-five collections use the shared lifecycle transition map. Hook code resolves role slugs from server accountability, validates selected payloads and tenant references, records transitions, applies domain calculations, and defines two scheduled jobs. The eleven scoped collections also use the fail-closed operator mapping/grant adapter described below; create and update payloads validate known farm, plot-through-farm, crop-cycle, harvest, and location-qualified staff references using the request database context. | Hook-by-hook parity against native service paths, execution/retry behavior under the deployed Directus image, and authenticated before/after database evidence. |
| Tenant and Field Collector gates | Permission SQL plus [`directus-authorization.ts`](../../extensions/kokonut-hooks/src/directus-authorization.ts) and [`tests/test_directus_tenant_permissions.py`](../../tests/test_directus_tenant_permissions.py) | The hook maps the authenticated Directus user’s `external_identifier` to an enabled Kokonut operator by exact configured OIDC issuer and subject. For eleven location-scoped collections, including `revenue_event`, it adds a grant-derived location predicate before reads and checks all create/update/delete targets using the request transaction. It now rejects `deep` query objects and nested/wildcard relation fields until each related collection has an explicit scope contract. Field Collector-origin farm-activity reads remain excluded from Directus. | Pinned-image behavior under `kokonut_directus_runtime`, role/field parity, effective denial of nested relations, bulk-query cases, live issuer/identity/grants, revocation/transfer concurrency, and confirmation every Field Collector path stays on Gateway. This hook check is not PostgreSQL RLS or a signed tenant-context boundary. |
| Schema metadata | [`tests/test_directus_metadata.py`](../../tests/test_directus_metadata.py) and [`schemas/directus/snapshots/schema_latest.json`](../../schemas/directus/snapshots/schema_latest.json) | The checker compares snapshot sort fields and physical field metadata, and can query the local Compose database when it is running. | Permission parity, API response shape, current runtime identity, or whether the optional Directus profile is deployed. |
| Native replacement surface | [`services/gateway/router.py`](../../services/gateway/router.py), [`services/gateway/operator_auth.py`](../../services/gateway/operator_auth.py), [`services/gateway/farm_activity_roles.py`](../../services/gateway/farm_activity_roles.py), and the [Gateway farm-activity contract](gateway-farm-activity-operations.md) | Native routes cover a bounded public read surface and selected authenticated reviewer, Field Collector, and farm-activity operations. Farm-activity templates expand into explicit tenant-qualified grants; Analyst reads are verified/published-only. Migration 404 adds a separate append-only operator event ledger for non-Field-Collector operations. | This is scoped support for the native Field Collector workflow and non-Field-Collector `farm_activity` records, not every Directus collection/field/relation, administrative UI, hook side effects, or schedules. Migration rollout and historical-row reconciliation are open. |

The 13 October pinned-image probe found that the archived `directus_users`
table had no `location_id` column while staff filters referenced it. Synthetic
Field Worker requests were denied and exposed no rows, which was fail-closed
but did not prove own-location access or cross-location isolation. The 15
October source repair now removes that obsolete predicate and create
validation, preserving unrelated status/business conditions and delegating
tenant scope to the explicit grant hook. Its transformation passed an
idempotent PostgreSQL 16 disposable check, including rejection of an
unexpected filter shape. This does not prove the required hook is loaded in a
running Directus deployment or that effective API permissions match the
Gateway ([evidence](builds/2026-10-15-recovery/directus-org-location-permission-contract.json)).

The source hook now resolves `directus_users.external_identifier` as the OIDC
subject and requires an exact `KOKONUT_OPERATOR_OIDC_ISSUER` match to an enabled
`operator_identity`; Directus receives the same issuer setting as the Gateway.
For each of the eleven location-scoped collections, it adds
the active organization-qualified `operator_scope_grant_allows` locations to
the `items.query` filter and checks returned `items.read` IDs against their
stored locations, even when the caller did not request the `location_id` field;
create requires a non-null location and a `create` grant; update/delete load
every requested row and require a matching grant for its existing location.
Bulk operations fail as a whole if any key is unknown or out of scope, and an
update cannot move a row between locations. These checks use Directus's
request transaction where the extension event context provides it. Missing
issuer, unauthenticated users, unmapped subjects, missing grants, and global
tenant creates fail closed. Directus API grants use resource = collection and
action = `read`, `create`, `update`, or `delete`; they are not auto-created or
translated from workflow actions. Legacy grants with a null organization are
excluded even though the shared compatibility function still accepts them for
some existing Gateway paths. Provision Directus grants only after role/field
parity is reconciled. No provider, operator, or Directus grant has been
configured.

This is a top-level source guard, not a completed tenant boundary. The source
adapter now rejects `deep` query expansion and dotted or nested wildcard field
paths for tenant-scoped collections because related objects do not yet have
explicit grant contracts. This closes the unreviewed relation-expansion path
at the source hook; pinned-image denial and field allowlists still need
effective-API checks. The legacy
Compose service still runs as a database superuser, and the code does not
establish the signed transaction context required for PostgreSQL RLS. The new
candidate role acceptance covers DML, DDL denial, stale explicit ACL removal,
future-object defaults, and database isolation only. A grant/share/owner
revocation race also remains outside this hook's proof. Do not enable RLS or
claim Directus parity from unit/source checks. The
hooks use Directus's documented `items.query` and `items.read` filter events
with request transaction/accountability context; confirm those semantics under
the pinned image in isolated runtime acceptance
([Directus hook event docs](https://docs.directus.io/extensions/hooks); [role evidence](builds/2026-10-15-recovery/directus-runtime-role-disposable.json)).

The Directus create-time reference validator rejects malformed explicit
`location_id` values and checks referenced plots/cycles/harvests against the
same request transaction. Tenant authorization now separately requires a
location-scoped operator grant. The directus-specific grants and provider
mapping still require isolated API acceptance; nullable historical rows remain
subject to each collection's policy and cannot be created by this hook.

The SQL still grants `fields = '*'` on many read rules, so a row predicate does
not establish field privacy. The Auditor policy deliberately has unfiltered
reads for collections beyond the eleven-collection tenant-hook list,
including reporting and governance records. Confirm that this global forensic
scope is intended before replacing it with tenant-scoped native routes; do not
silently narrow it or call it equivalent to the native operator grants.

The hook source also has effects beyond request validation: NOI snapshot
recalculation, financial projection writes, lifecycle history, and daily/weekly
scheduled callbacks. The daily 02:00 callback calls the snapshot upsert path
for every active crop cycle through the Directus database connection; it does
not establish a location-scoped worker identity. Its batch result now counts
successful and failed crop-cycle reconciliations separately, and the schedule
reports partial failure explicitly instead of presenting a success count that
omits failed cycles. A separate default-off native NOI worker already
reconciles one explicitly granted location at a time.

The weekly `0 3 * * 0` callback reads verified, source-eligible
`farm_activity`, groups by week and location, and discards the result. It does
not create or update snapshot records. Its log now says exactly how many
location-week result rows were returned and explicitly says that no snapshots
were persisted; this corrects an earlier success message that implied durable
output. Whether this is an unfinished placeholder or an intended read/report
capability still needs an owner decision. The daily Directus callback, native
NOI worker, and weekly query need separate ownership, scope, overlap, and output
parity decisions before any schedule is enabled, transferred, or disabled.

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

The optional hook extension now bounds its failure logs to exception class
names for role lookup, workflow-history logging, NOI calculations, and both
scheduled callbacks. Raw exception objects and their messages are no longer
written by those handlers. Four focused Vitest checks and TypeScript type
checking pass. This improves log hygiene without changing hook failure,
schedule, or retry behavior; it does not establish hook output parity, runtime
identity, or schedule ownership.

The owner selected organization/location grants and source now maps the
authenticated Directus external subject to a Kokonut operator. In the pinned
image, the synthetic Field Worker sees a Field Note in its granted location
and cannot see the cross-location Field Note; this confirms the loaded read
hook works on a permission-compatible collection. `farm_activity` remains
denied even in the own location because its role-linked rows use custom
permission rules that the unlicensed API hides. The owner selected Gateway
operations while keeping Directus optional. The Gateway now provides explicit
per-location role templates for Field Worker, Supervisor, Manager, Finance,
Analyst, and Auditor, atomic provisioning that checks active tenant membership
plus current owner/share state, and verified/published-only Analyst routes.
Canonical activity detail uses its own `farm_activity:read_detail` grant;
private capture detail remains a separate mobile-review permission. Migration
404 now adds a separate native Gateway API for non-Field-Collector
`farm_activity` records: scoped list/detail, draft create/edit, and
submit/verify/reject/rework/publish/exception-close with an append-only actor
ledger. Thirteen focused service/HTTP/policy tests and 11 disposable PostgreSQL
checks pass. This does not automatically adopt historical rows without Gateway
actor history; those lifecycle transitions fail closed pending reconciliation.
Other collection CRUD, complete field/relationship parity, Directus admin UI,
hook side effects, and scheduled-job ownership remain open. No Directus
permission was broadly enabled, migration 404 was not applied to the candidate,
and no live provider/account was configured. The earlier 104 focused
role/route/query/lifecycle tests and four disposable PostgreSQL
role-provisioning checks also pass; all disposable fixtures use no candidate or
legacy data
([evidence](builds/2026-10-16-recovery/farm-activity-gateway-role-mapping.json);
[PostgreSQL runner](../../scripts/check-farm-activity-role-grant-disposable.py);
[operations contract](gateway-farm-activity-operations.md);
[migration evidence](builds/2026-10-16-recovery/gateway-farm-activity-operations-disposable.json)).

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

## Organization/location grant fixture — 15 October 2026

The Directus seed no longer creates `$CURRENT_USER.location_id` filters or
create validations. Its idempotent repair removes only that exact obsolete
clause from previously seeded permissions, preserves other predicates such as
draft-only updates, and aborts if it encounters an unexpected filter shape.
The permission repair passed a disposable PostgreSQL 16 check for predicate
preservation, repeat application, and fail-closed handling. The tenant hook
now also includes `revenue_event`, the eleventh collection covered by the old
location-scope repair.

The isolated API fixture now checks for the grant schema and selects two
locations with the same active verified owner. It creates one synthetic
operator, organization membership, one-location read/create/update grants,
and a mapped Directus Field Worker account. It then attempts own-scope and
cross-scope requests and removes all fixture records. The recovery Compose
profile mounts the built hook and sets the same synthetic issuer in the runtime
and fixture. Five focused Python checks pass; the extension suite passes 61
tests and the TypeScript build passes. The pinned API check confirms effective
own/cross Field Note reads through the hook, but `farm_activity` has no
effective permissions and returns 403 for both own and cross access. The
associated Field Worker rows have custom source/item filters and field limits.
The pinned Directus source removes unlicensed custom-rule rows from its
permission service, and official documentation describes the same behavior
for unlicensed instances ([access control](https://directus.com/docs/guides/auth/access-control); [unlicensed permission limitations](https://directus.com/docs/guides/environment-sync/secrets-and-limitations)).
The synthetic identities and rows were removed; candidate and legacy databases
were untouched. No field-privacy, relation, create/update, licensed-runtime, or
schedule parity is claimed
([evidence](builds/2026-10-15-recovery/directus-org-location-permission-contract.json)).
