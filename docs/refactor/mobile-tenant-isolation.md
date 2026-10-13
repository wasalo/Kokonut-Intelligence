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
   immutability or audited transfer semantics are in place.

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
   before interpreting row counts. The
   local candidate run found zero locations and zero inventoried rows; it is
   empty and cannot establish ownership for a populated deployment ([sanitized
   evidence](builds/2026-10-13-recovery/field-collector-tenant-preflight.json)).
2. Have accountable data owners resolve the ownership map and define audited
   organization-transfer and explicit-sharing semantics. Unresolved records
   remain outside tenant-protected APIs until resolved.
3. Add server-managed organization membership and tenant-aware grants while
   preserving existing location-grant compatibility. Test provisioning,
   revocation, and cross-tenant denial before changing RLS.
4. Add transaction-local context to each service/worker connection path, then
   add additive RLS policies and indexes through new ordered migrations. Keep
   existing migrations immutable.
5. Verify through the same least-privilege role used by the application:
   missing context denies; organization A cannot select or mutate organization
   B; same-location partner access requires an explicit share; revoked grants
   stop access; pooled connections do not retain prior context; workers cannot
   bypass scope; and every downstream mobile consumer checks
   `v_mobile_collection_use_eligibility` before reporting or publication.
6. Take an encrypted checkpoint, rehearse upgrade and rollback on a restored
   copy, and only then roll out to the local candidate. Keep the current
   location-grant checks in place throughout migration.

## Current acceptance state

The content-free disposition inventory passes focused service/query,
dual-grant authorization, and console checks. A separate read-only ownership
preflight CLI is implemented and ran successfully against the local candidate,
which returned zero locations and zero inventoried rows. This confirms only
that the candidate is empty; it does not establish ownership for a populated
deployment. These steps prove only known direct lineage and the inventory's
location-scoped contract. Organization ownership reconciliation, tenant-aware
operator membership/grants, RLS, worker isolation, and downstream consumer
parity remain open. No RLS migration or live data mutation was made.
