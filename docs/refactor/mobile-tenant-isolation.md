# Field Collector tenant and row-isolation boundary

Updated: 13 October 2026. This is the target security contract for tenant
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
6. For new tenant-owned rows, store an explicit tenant key or enforce an
   equivalent immutable parent relationship. For existing location-bound
   rows, RLS may resolve the tenant through the location only after ownership
   immutability or audited transfer semantics are in place. Migration 390 and
   the local operator CLI now implement a pending/accepted/cancelled transfer
   with separate source and target administrators. Its focused database
   acceptance and candidate rollout remain open; see the
   [transfer contract](tenant-owner-transfer-contract.md).

## RLS and connection-context requirements

RLS is a second enforcement layer behind the service authorization checks. It
must be introduced only with tenant-aware request context and production-role
verification:

- Set tenant, location, actor ID, and actor type with transaction-local
  settings after authentication. Validate them against stored membership and
  grants in the same transaction. Never use session-wide settings that can
  leak through pooled connections.
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
2. Resolve the seed-location ownership map before tenant backfill. The
   repository owner confirmed Kokonut Network as the exclusive owner of both
   Kokonut Adelphi and Kokonut Genesis on 2026-10-13. This decision applies only
   to those two repository seed locations; it does not assign owners to other
   locations or resolve unlocated report/dashboard rows. Explicit-sharing
   semantics are implemented. Migration 390 defines audited organization-
   transfer semantics; acceptance and candidate rollout remain open before RLS.
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
   The replay excluded archived data and pilot seeds; candidate rollout remains
   separately gated, and RLS is not enabled.
4. Migration 390 defines two-party audited owner transfers; run focused
   disposable PostgreSQL acceptance before any rollout. Unassigned/conflicted
   locations still require an accountable ownership decision and cannot use
   the transfer workflow. The transfer revokes prior shares and all active
   location grants so access must be reissued under the new owner.
5. Add transaction-local context to each service/worker connection path, then
   add additive RLS policies and indexes through new ordered migrations. Keep
   existing migrations immutable.
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
transfer workflow, but focused acceptance and candidate rollout remain open.
Least-privilege worker behavior and RLS remain open. The operator CLI
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
Clean full ordered replay has passed, but candidate rollout remains separately
gated. The operator CLI lifecycle and legacy-grant conversion passed separate
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
Candidate rollout and migration-390 transfer acceptance, transaction-local
tenant context, arbitrary direct-SQL isolation, and RLS remain open.
