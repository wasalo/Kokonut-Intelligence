# Field Collector tenant and row-isolation boundary

Updated: 16 October 2026. This is the target security contract for tenant
isolation. The current Field Collector remains location-scoped and does not yet
have database-enforced tenant RLS.

## Current source-of-truth boundary

- An enrolled mobile device is bound to a location. The API derives its
  location from the stored device/enrollment and does not trust a submitted
  tenant identifier.
- OIDC operator grants are explicit per resource, action, and location. The
  operator console cannot turn a browser-supplied organization or location into
  authority.
- `location.organization_id` exists, but it is nullable. It is a candidate
  primary-organization assignment, not evidence that every row has a known
  tenant.
- `organization_member` relates organizations to locations and optional farms;
  its `owned`, `affiliated`, `sponsored`, and `partner` relationship types do
  not identify an authenticated human or independently grant data access.
- Mobile records carry location scope, not a general `tenant_id`. Their current
  safety depends on API-derived device scope, explicit operator grants, and
  queries that bind records and grants to the same location.

Therefore, a location is not a tenant ID, an organization relationship is not
an operator grant, and a missing organization must never fall back to global
access. No current mobile route claims general database RLS protection.

## Target tenant model

1. Treat the organization as the security tenant and a location as an
   operational scope within that tenant. Keep resource/action/location grants
   as the finer-grained authorization boundary.
2. Use `location.organization_id` as the primary tenant owner only after an
   audited reconciliation establishes its meaning and confirms it agrees with
   the intended owner relationships. Do not infer a tenant from an arbitrary
   `organization_member` row, even when its role is `primary` or its type is
   `owned`.
3. Preserve one primary tenant owner for tenant-owned records. Partner or
   affiliate access must be a separate, explicit, revocable sharing grant; it
   must not transfer ownership or make every organization attached to a
   location a tenant owner.
4. Bind each OIDC operator to organization membership through a server-managed
   identity record. A tenant-aware operator grant must include a tenant and a
   location, and grant provisioning must verify that the location belongs to
   that tenant. Browser claims and request parameters are selectors only.
5. Bind mobile enrollment to the validated tenant owner as well as the
   location. If the owner is missing, conflicted, or changes, preserve the
   existing device/location behavior but deny tenant-protected operations
   until an accountable owner resolves the mapping. Do not silently retag
   historical collections.
6. The repository owner confirmed Kokonut Network as the operating tenant for
   Genesis, Seeds, Adelphi, Terra Viva, and V1. Seed 122 reconciles only exact
   existing name/slug matches and leaves missing future source records absent;
   the read-only tenant preflight reports aggregate presence/verification
   counts without returning names or identifiers. This does not establish
   legal land title or map additional locations
   ([reconciliation procedure](tenant-owner-map-reconciliation.md)).
7. For new tenant-owned rows, store an explicit tenant key or enforce an
   equivalent immutable parent relationship. For existing location-bound
   rows, RLS may resolve the tenant through the location only after ownership
   immutability or audited transfer semantics are in place. Migration 390 and
   the local operator CLI now implement a pending/accepted/cancelled transfer
   with separate source and target administrators. Fourteen focused disposable
   PostgreSQL transfer/context checks passed, and the candidate rollout applied
   migrations 387–390 after a fresh encrypted checkpoint. See the
   [transfer contract](tenant-owner-transfer-contract.md) and
   [rollout evidence](builds/2026-10-14-recovery/candidate-tenant-transfer-rollout.json).

## RLS and connection-context requirements

RLS is a second enforcement layer behind the service authorization checks. It
must be introduced only with tenant-aware request context and production-role
verification:

- Set tenant, location, actor ID, and actor type with transaction-local
  settings after authentication. Validate them against stored membership and
  grants in the same transaction. The mobile-device path now uses migration
  393's database-signed context accessor; custom GUC labels alone remain
  untrusted. Never use session-wide settings that can leak through pooled
  connections.
- Policies fail closed when context is absent, malformed, revoked, or
  inconsistent with the row's tenant/location. Read and write policies are
  distinct; a location grant alone cannot satisfy an organization boundary.
- Application roles must not have `BYPASSRLS`. Use a separate migration/admin
  role. Apply `FORCE ROW LEVEL SECURITY` where table-owner behavior would
  otherwise bypass policies, and verify views use invoker security or an
  explicitly reviewed safe boundary.
- Keep background workers explicit: each job carries a validated tenant scope
  or uses a narrowly documented cross-tenant service role. Do not make generic
  worker access an implicit bypass.
- Do not enable RLS on existing production tables until all unmapped or
  conflicting locations and records have a reviewed disposition. There is no
  automatic default tenant and no broad backfill from `organization_member`.

The first source integrations cover the optional Gateway report-review and
Field Collector review queue/detail reads. Each validates a tenant-qualified
grant and sets transaction-local context on the same connection and read-only
transaction as the protected query. The content-free disposition inventory
validates its retention and review grants together and rejects them if they
resolve to different tenants. Legacy NULL-tenant grants receive HTTP 403 until
operator affiliation and tenant grants are provisioned. Twenty-two synthetic
disposable PostgreSQL checks and 31 focused context, mobile service, and route
checks passed, including owner/shared reads, context-before-query, cleanup,
same-tenant multi-grant acceptance, cross-tenant denial, and pre-query legacy
denial
([evidence](builds/2026-10-14-recovery/tenant-owner-transfer-context-disposable.json)).
Source now also applies transaction-local context to canonical farm-activity
intake, list/detail, draft promotion/correction, and lifecycle operations; OIDC
mobile-device enrollment/revocation; OIDC participant-link creation/revocation;
and append-only mobile reviewer-note writes. The public API-key enrollment and
participant endpoints retain their separate Gateway capability checks.

Migration 391 pins each new enrollment code and registered device to the
location's active verified owner. It deliberately leaves existing rows NULL;
there is no safe evidence in a legacy device row to infer which owner enrolled
it. Device-token forms, private-media policy and metadata writes, collection
sync, and sync-status now set the tenant context in the same transaction as
their protected query. The context validates the active device, current owner
verification, and pinned organization, and holds a share lock on the location
and owner rows until the transaction ends. Owner transfer therefore waits for
in-flight protected work and makes old-owner devices fail closed afterward.
An unused enrollment code is also rejected if its pinned owner is no longer
current.

Migration 393 signs the mobile context with a database-private HMAC key and
binds it to the current PostgreSQL backend and transaction. RLS policies for
this path must read `kokonut_security.current_tenant_context()`; setting
`kokonut.tenant_id` or related labels directly does not establish access. A
network-disabled PostgreSQL 16 disposable acceptance applied and replayed
migrations 392–393, forced RLS on synthetic tables, and passed owner scoping,
cross-tenant filtering, signature-tampering denial, invalid-token cleanup,
key-table denial, and transaction reset. The migration adds only dormant
policies and does not enable application-table RLS. The candidate remains at
migration 391; OIDC operator and Gateway context still need an equivalent
database-verifiable boundary. See the [RLS call-site audit](mobile-tenant-rls-callsite-audit.md)
and [acceptance evidence](builds/2026-10-14-recovery/mobile-tenant-context-proof-disposable.json).

The browser recognizes the dedicated re-enrollment denial, removes only the
old device credential and cached forms, and flags the existing encrypted queue
for owner review. It preserves each queued payload and photo and excludes those
records from later sync, including after a new owner-approved device enrollment.
New records collected after that enrollment belong to the new device. Existing
legacy device rows and pending enrollment codes require fresh enrollment;
synced server records remain unchanged for reviewer disposition. No ownership
or collection rows are automatically retagged or deleted.

This covers only the bounded operator surfaces listed above; remaining Gateway
routes, background workers, Directus, direct database consumers, and RLS remain
open. The 13 October owner-bound device slice passed 67 focused Python checks,
two offline-shell Node checks, Ruff, Python syntax, dependency alignment, and
provider-boundary checks. Migration 391 replayed twice in a disposable
PostgreSQL 16 database; old rows stayed unbound, owner mismatch inserts and
binding updates failed, and a former-owner device no longer matched the
protected-access predicate after transfer. Candidate rollout then applied
migration 391 after a fresh age-encrypted checkpoint; only the app was recreated,
health returned 200, and anonymous farm-activity/review routes returned 401.
The empty candidate had no location, transfer, device, or enrollment records, so
this verifies deployment and route protection rather than populated ownership
or re-enrollment behavior. The encrypted checkpoint was restore-rehearsed into
an isolated template0 target, with all 381 pre-391 schema fingerprints,
extension versions, and selected aggregate counts matching; see the
[rollout evidence](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json).
An isolated Chrome context has now verified app-shell reopen and encrypted
queue capture with `navigator.onLine=false`, followed by queue preservation
through a mocked 503 and clearing after a mocked successful retry. This is
client offline behavior only; its mobile API calls were intercepted. Live
authenticated re-enrollment, tenant API sync, populated transfer behavior, and
human retention/erasure disposition remain open. RLS remains disabled.

## Ordered implementation and acceptance

1. Inventory active and inactive locations, `location.organization_id`,
   organization relationships, mobile devices, collections, media, and
   downstream rows. Report null owners, disagreements, shared locations, and
   rows whose source cannot be assigned. Keep this read-only. The source preflight is available
   as `python3 -m services.cli mobile-tenant-preflight [--location-id UUID]`;
   it emits opaque references and aggregate relation counts, never performs an
   owner backfill, and labels unlocated-record totals as database-wide. The
   command checks required schema columns first. Older/partial schemas return
   `schema_incomplete` with missing columns and latest migration context when
   available, without querying inventory rows; use an isolated migrated copy
   before interpreting row counts. This gate passed against a fresh populated
   restore: it reported two locations and 376 migration-history rows in a
   separate aggregate check, listed 11 missing columns, and returned no
   ownership/lineage counts
   ([incomplete-schema evidence](builds/2026-10-13-recovery/field-collector-tenant-preflight-schema-gate.json)).
   The complete-schema branch also returned all 27 required columns and
   migration 385 on the empty candidate
   ([complete-schema evidence](builds/2026-10-13-recovery/field-collector-tenant-preflight-schema-complete.json));
   that candidate does not establish populated ownership. The earlier local
   candidate inventory found zero locations and zero rows
   ([candidate evidence](builds/2026-10-13-recovery/field-collector-tenant-preflight.json)).
   The current source additionally requires 46 columns and the shared
   `operator_scope_grant_allows` database predicate before querying inventory.
   It reports aggregate enabled/disabled operator and membership totals plus
   per-location legacy and tenant-qualified grant state, without operator or
   tenant IDs. A schema-targeted disposable fixture using actual migrations
   388 and 391 passed focused checks and verified cleanup; see the
   [aggregate evidence](builds/2026-10-13-recovery/tenant-preflight-operator-access-disposable.json).
   These database-wide identity counts are sizing information only; they do not
   resolve the real affiliation mapping or convert any legacy grant.
2. Resolve the seed-location ownership map before tenant backfill. The
   repository owner confirmed Kokonut Network as the exclusive owner of both
   Kokonut Adelphi and Kokonut Genesis on 2026-10-13. This decision applies only
   to those two repository seed locations; it does not assign owners to other
   locations or resolve unlocated report/dashboard rows. Explicit-sharing
   semantics are implemented. The candidate now has all 382 schema migrations
   through 391 applied and zero pending schemas; 121 seed files remain
   pending in the migration ledger. Its location table is empty, so migration 387
   created the canonical Kokonut Network organization without creating
   location ownership evidence. Five mobile-form rows and ten revisions are
   present without applied seed history, so seed rollout requires reconciliation
   first. Worker isolation and RLS remain open.
3. Add server-managed organization membership and tenant-aware grants while
   preserving existing location-grant compatibility. Source foundation is in
   migration 388: tenant grants require an active operator membership plus a
   current verified location owner or explicit share; share creation/revocation
   requires an owner-side tenant administrator; revocation also revokes the
   corresponding tenant grants. Existing NULL-tenant location grants remain
   compatible and are not backfilled because their operators' tenant
   affiliations are not known. Focused migration and authorization checks now
   pass on a network-disabled disposable PostgreSQL 16 database for actual
   migrations 387–389, including idempotent replay of 388–389 and positive and
   negative Field Collector trigger cases. A second disposable run exercised
   CLI membership/share lifecycle, dependent revocation, and legacy-grant
   conversion. A separate clean full-schema replay applied all 380 ordered
   migrations with zero pending or failed, including the combined 384–385–389
   trigger stack and 11 registered activity/workflow triggers
   ([evidence](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json)).
   The replay excluded archived data and pilot seeds. Candidate migrations
   387–391 have now been applied after a fresh age-encrypted checkpoint; only
   the app was rebuilt/recreated. The app, database, and Metabase are healthy,
   the proxy remains running, and anonymous farm-activity and mobile-review
   routes return 401. The candidate has no locations, transfers, devices, or
   enrollments; seed reconciliation and populated owner/device acceptance remain
   open. See the [tenant-binding rollout evidence](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json); RLS is not enabled.
4. Migration 390 defines two-party audited owner transfers. Fourteen focused
   disposable PostgreSQL 16 checks passed for request/approval, stale and
   conflicting ownership, cancellation, atomic rollback, prior-access
   revocation, fresh grant issuance, audit immutability, and replay
   plus owner/shared context, ambiguous-grant uniqueness, legacy-grant denial,
   and transaction reset
   ([evidence](builds/2026-10-14-recovery/tenant-owner-transfer-context-disposable.json)).
   Unassigned/conflicted locations still require an accountable ownership
   decision and cannot use the transfer workflow. The transfer revokes prior shares and all active location
   grants so access must be reissued under the new owner.
5. Add transaction-local context to each service/worker connection path, then
   add additive RLS policies and indexes through new ordered migrations. Keep
   existing migrations immutable. Initial source groundwork is in
   `services/common/tenant_context.py`: it clears previous local values, derives
   tenant/location/actor from an active tenant-qualified grant, verifies that
   grant through the migration-388 database predicate, and sets the values with
   transaction-local `set_config`. Eight unit tests and the disposable database
   context checks pass, including legacy-grant denial, context clearing on
   denial, and reset at commit. The helper is not yet integrated into all
   request or worker transactions, and RLS remains disabled.
6. Verify through the same least-privilege role used by the application:
   missing context denies; organization A cannot select or mutate organization
   B; same-location partner access requires an explicit share; revoked grants
   stop access; pooled connections do not retain prior context; workers cannot
   bypass scope; and every downstream mobile consumer checks current
   Field Collector eligibility before reporting or publication. Migration
   386 adds the canonical activity predicate and source-level consumer filters;
   focused PostgreSQL 16 synthetic acceptance and 56 application/query/console
   checks pass. The full ordered replay passed on a fresh populated archive
   clone. Migration 386 is also deployed on the local candidate after a fresh
   encrypted checkpoint restore rehearsal; only the app was recreated and its
   protected routes still return 401 anonymously ([rollout evidence](builds/2026-10-13-recovery/candidate-farm-activity-use-gate-rollout.json)).
6. For future tenant/RLS migrations, take an encrypted checkpoint, rehearse
   upgrade and rollback on a restored copy, and only then roll out to the local
   candidate. Keep the current location-grant checks in place throughout.

## Current acceptance state

The content-free disposition inventory passes focused service/query,
dual-grant authorization, and console checks. A separate read-only ownership
preflight CLI is implemented and ran successfully against the local candidate,
which returned zero locations and zero inventoried rows. This confirms only
that the candidate is empty; it does not establish ownership for a populated
deployment. These steps prove only known direct lineage and the inventory's
location-scoped contract. Ownership outside the two confirmed seed locations,
RLS, worker isolation, and downstream consumer parity remain open. The
operator CLI membership/share lifecycle and legacy-grant conversion now have
separate disposable acceptance evidence. No RLS migration or live data
mutation was made.

On 13 October 2026 the preflight also ran against a fresh isolated copy of the
populated archive after the ordered migration runner applied all 32 pending
schemas through migration 385; the final schema plan had zero pending entries.
The corrected inventory found two locations and no active organization-member
rows. One location has a direct organization assignment without a confirming
active owned-primary relationship; the other is unassigned. It counted four
mobile devices and five location-scoped dashboard datasets, plus three report
snapshots and 38 dashboard datasets with no location. No identifiers were
retained in evidence, and no owner was inferred or backfilled. The replay also
exposed and fixed UUID-array decoding that had generated false opaque owner
references; the corrected query casts to `text[]` and fails closed for an
unexpected driver shape. See the [sanitized replay evidence](builds/2026-10-13-recovery/field-collector-tenant-populated-migration-replay.json).

The account owner has resolved both seed-location owner records: Kokonut
Network owns Adelphi and Genesis exclusively. The source implementation is
migration 387 plus the final `seed-pilot.sh` ownership seed. Unlocated report
and dashboard rows remain unassigned after a read-only lineage review found no
location or confirmed-tenant reference that establishes their owner. This
review covers the 38 unlocated dashboard definitions and three unlocated draft
snapshots on the retained archive clone; it does not claim complete downstream
lineage. The clean-schema replay of all 380 migrations, including the
384–385–389 trigger stack, has now passed; this did not include archived data
or pilot seeds. Migration 390 and the local CLI now implement a two-party
transfer workflow; focused acceptance and the separately approved local
candidate rollouts through migration 391 have passed. The candidate has 382
applied schemas through 391 and 120 pending seeds; `seed:140_mobile_forms.sql`
is recorded after exact source parity, with no business-row changes. The
candidate still has no location rows. Least-privilege worker behavior and RLS
remain open. The operator CLI
membership/share lifecycle and legacy-grant conversion passed separate
disposable acceptance; RLS is not enabled by this ownership reconciliation
([lineage evidence](builds/2026-10-13-recovery/reporting-tenant-lineage-review.json); [replay evidence](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json); [transfer contract](tenant-owner-transfer-contract.md)).

## Confirmed seed-location owner mapping — 13 October 2026

The repository owner confirmed exclusive Kokonut Network ownership for
Kokonut Adelphi (`a0000000-0000-0000-0000-000000000001`) and Kokonut Genesis
(`a0000000-0000-0000-0000-000000000002`). The implementation creates/resolves
the SQL `organization` row with `org_key = 'kokonut-network'`, applies a
narrowly-scoped, fail-closed ownership migration, and re-applies the mapping
after all pilot seeds so Genesis is present. The historical Kokonut Adelphi
organization row and non-owner relationship types remain intact. Active
`owned` relationships for these two locations converge on one primary Network
relationship each. This does not assign ownership to other locations, retag
unlocated reports/dashboards, provision user access, or enable RLS. Migration
and seed acceptance passed on a network-disabled disposable PostgreSQL 16
compatibility fixture, including idempotent replay, clean-bootstrap ordering,
deactivation of the observed legacy owner link, and refusal/rollback on an
unrelated owner ([evidence](builds/2026-10-13-recovery/tenant-ownership-disposable-acceptance.json)).
Full ordered-migration replay and candidate rollout remain separate gates; the
mapping decision alone does not authorize a candidate rollout.

## Tenant-aware operator grant foundation — 13 October 2026

Migration 388 adds an explicit owner-verification ledger for the two confirmed
seed locations, server-managed OIDC operator-to-organization memberships,
revocable location shares, and an optional organization tenant on
`operator_scope_grant`. New tenant-qualified grants require an active operator
membership and either the verified owner organization or an explicit share.
Only a tenant administrator of the verified owner organization may create or
revoke a share through the local operator CLI; share and membership revocation
also revokes the associated tenant-qualified grants. Request authorization and
the in-query report, mobile-review, and farm-activity grant checks now use the
same database predicate.

The migration does not infer operator affiliations from old location grants.
Legacy NULL-tenant grants continue to use the existing explicit
location-scoped contract until each identity is reconciled. Tenant grants are
not a claim of row-level isolation: transaction-local context, worker scoping,
transfer workflow, and direct database privilege boundaries remain open.
Clean full ordered replay has passed, and migrations 387–390 are now applied
to the local candidate after a fresh encrypted checkpoint. No location rows or
pilot seeds were present there. The operator CLI lifecycle and legacy-grant conversion passed separate
disposable acceptance. Focused
predicate and trigger acceptance has passed on a minimal
compatible disposable PostgreSQL schema. RLS remains disabled.

### Field Collector write-trigger follow-up — 13 October 2026

Migration 389 adds tenant-aware grant checks to the Field Collector draft
insert, content-edit, and lifecycle-event trigger paths created by migrations
384–385. The new guards call the migration-388 shared authorization predicate,
which preserves the explicit compatibility behavior for existing NULL-tenant
location grants. Earlier applied migrations remain unchanged.

### Disposable migration acceptance — 13 October 2026

The actual SQL for migrations 387, 388, and 389 passed in order against a
network-disabled disposable PostgreSQL 16 instance; migrations 388 and 389
also passed an idempotency replay. Authorization checks covered the confirmed
owner, a partner requiring an active share, expired/revoked shares, revoked
membership, inactive organization, disabled identity, revoked grant, stale or
missing owner verification, and legacy NULL-tenant compatibility. Trigger
checks covered Field Collector draft insert, edit, submit and draft-edited
events, including denied cases when required grants were absent. Manual
records outside the targeted form identity remained unaffected. Sanitized
evidence is in
[`tenant-grants-migrations-disposable.json`](builds/2026-10-13-recovery/tenant-grants-migrations-disposable.json).

The authorization and CLI behavior runs used a minimal compatible schema.
A separate clean-bootstrap replay then applied the full ordered repository
chain: all 380 migrations succeeded with zero pending or failed, and the
384–385–389 trigger stack registered all 11 expected activity/workflow
triggers. The candidate remained healthy and untouched; the disposable
container, network, and volume were removed. This does not verify populated
archive data or pilot seeds. See
[`tenant-grants-full-schema-replay.json`](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json)
and the separate operator CLI evidence
[`tenant-grants-cli-disposable.json`](builds/2026-10-13-recovery/tenant-grants-cli-disposable.json).
Migration-390 transfer and context acceptance passed against a disposable
database (14 database checks plus eight context unit tests). Its candidate
rollout applied four pending schemas, recreated only the app, and verified
service health and protected routes. Initial transaction-local operator-context
helper source is present and tested, but integration into Gateway/worker
connection paths, arbitrary direct-SQL isolation, and RLS remain open.
