# PostgreSQL runtime-role policy

Status: opt-in application and operator-auth roles are implemented. Operator
session, mobile credential, and bounded device-revocation boundaries passed
disposable PostgreSQL 16 role checks, including forced RLS; the synthetic and
populated-restore role fixtures use the second credential. Separate Directus, Metabase metadata, and
analytics-source role boundaries also passed on isolated populated copies. No
candidate or legacy ACL was changed by these role fixtures. Separately,
migrations 392–400 were applied schema-only to the local candidate after an
encrypted checkpoint; its application-table RLS remains
disabled. The candidate still connects as the `kokonut` superuser because
dedicated runtime credentials are not provisioned.
Metabase dashboard/source parity and full domain-workflow acceptance remain open; see
[optional consumer roles](optional-database-roles.md).

## Role boundary

`POSTGRES_PASSWORD` remains the migration/operator credential for the database
owner. Application code now reads `PG_PASSWORD` first and falls back to
`POSTGRES_PASSWORD` for existing deployments. The candidate can use the
dedicated `KOKONUT_RUNTIME_USER` and `KOKONUT_RUNTIME_PASSWORD` variables when
combined with `docker-compose.kernel-runtime-role.yml`; the app receives only
`PG_USER` and `PG_PASSWORD`, while the one-shot bootstrap receives the admin
credential.

The bootstrap requires a dedicated Kernel PostgreSQL instance and distinct
runtime and operator-auth passwords of at least 24 characters. It creates or
normalizes both roles as `LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
NOREPLICATION NOBYPASSRLS`, and refuses to reuse roles that own database
objects. It removes their role memberships, revokes `PUBLIC CONNECT` on
connectable databases and `CREATE` on the `public` schema, then grants both
roles `CONNECT` only to the selected database. The runtime role receives
`USAGE` on `public`, DML on public tables and sequence use that exist when the
bootstrap runs. The bootstrap revokes global and `public`-schema default
privileges for future tables and sequences, so newly created objects fail
closed until a reviewed grant is added. Do not rerun the broad bootstrap simply
to grant a new table: it re-grants DML to every public table present at that
time. The two
mobile credential tables replace that broad table grant with explicit column
grants: the app can read non-credential device and enrollment fields and
perform only the writes used by current mobile handlers. It cannot read
`mobile_device.device_token_hash`, `mobile_device.push_token`, or
`mobile_device_enrollment.code_hash`; it cannot insert or delete devices,
delete enrollments, or edit enrollment credential hashes. Operator sessions
have no table or column privileges and their functions cannot be executed by
the general runtime role.

Migration 395 creates a `NOLOGIN` function owner with only the table and column
rights needed for session creation, authentication, and revocation. The
separate `kokonut_operator_auth` login receives explicit `EXECUTE` grants on
those three functions. The Gateway's OIDC provider uses this credential for
session operations; scope lookup and application queries continue through the
ordinary runtime connection. The operator-auth role cannot directly read or
write the session table. Keep its password separate from the app, runtime, and database
owner credentials. It is a trusted authentication-service credential because
its session-creation function can issue sessions for provisioned enabled
identities.

The remaining runtime DML grant spans existing public tables other than operator
sessions and the two mobile credential tables. Mobile enrollment insertion and
device token revocation remain possible through the shared runtime role, so
this is not yet a database-verified Gateway capability boundary. It also does
not replace gateway authorization, row/field controls, or service-specific
review rules. Workers, the legacy CLI, Directus, views, and all other public
tables still need separately reviewed grants before RLS. Do not run this
bootstrap against the legacy stack or a database shared with unrelated
applications.

The [runtime SQL inventory](runtime-sql-inventory.json) records direct
execution sites across the whole `services/` tree to support that review. It
contains 3,799 call sites from 807 Python files and 1,034 regex-derived relation
candidates; literal SQLAlchemy `text()` and psycopg `SQL()` wrappers are
unwrapped. 111 statement kinds remain unknown, 23 statements begin
with `WITH`, 335 sites have no relation candidate, and 456 use a non-literal
query expression. Dynamic query construction, `WITH` semantics, ORM/provider
code,
columns, actual request reachability, and external Directus usage remain outside
its proof. It is a review map, not a grant list; convert no candidate relation
into an ACL until the call path, runtime principal, and operation are confirmed.

The grant boundary is for the native Kernel app and its workers. The current
legacy `docker-compose.yml` runs Directus with `DB_USER=kokonut` and
`DB_SEARCH_PATH=public,kokonut`; Metabase's metadata database also uses
`kokonut`. The recorded legacy role is a superuser. Neither service is part of
the standalone candidate or standard Compose profile, so this overlay does not
replace their database identities. Before either optional service is connected
to a Kernel database, use the separately tested Directus role and migration
policy, metadata-only Metabase role, and reviewed read-only analytics role.
These isolated role checks do not add either product to a Kernel profile.
Directus API permissions remain an independent authorization layer.

The bootstrap revokes `PUBLIC CONNECT` across every database in its PostgreSQL
instance. That is instance-wide and can affect any non-superuser identity on the
server, so the dedicated-instance requirement is a hard precondition. The
populated restore contained the legacy `kokonut` superuser plus the new runtime
role; candidate and legacy instances were not targeted.

## Enable on a fresh or restored candidate

Add `KOKONUT_RUNTIME_USER`, `KOKONUT_RUNTIME_PASSWORD`, and a separate
`KOKONUT_OPERATOR_AUTH_PASSWORD` to the encrypted secrets file. Keep the host
migration environment on the owner identity (`PG_USER=kokonut`, with
`POSTGRES_PASSWORD`); do not set either service password as the migration
CLI's `PG_PASSWORD`. Apply ordered migrations through 396 before provisioning
these roles. OIDC also requires the operator-auth role variables in the app
environment.

For a fresh isolated candidate, load encrypted secrets and provision before
starting the app or workers:

```sh
source scripts/load-secrets.sh
docker compose -p kokonut-kernel-candidate --env-file /dev/null \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-runtime-role.yml \
  --profile runtime-admin run --rm runtime-role-bootstrap
docker compose -p kokonut-kernel-candidate --env-file /dev/null \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-runtime-role.yml up -d app
```

For the split standard profile, include `docker-compose.kernel-standard.yml` in
both commands and start the `worker` after the bootstrap completes. Optional
HTTP, MQTT, and gRPC services read the same runtime variables when their
overlays are included. The standalone portability manifest remains on the
database owner credential until its separate role-bootstrap path is implemented.

Do not apply this native-app bootstrap to the currently running candidate until
its own rollout and full workflow acceptance are reviewed. A populated backup
and separate consumer grant plan now exist, but the helper still changes
instance-wide database ACLs and is not a Directus or Metabase provisioner.

## Isolated evidence and rollback

The internal-only recovery fixtures use a synthetic admin-owned table and a
second table created after provisioning. Existing-table compatibility is
verified with `SELECT`/`INSERT`/`UPDATE`/`DELETE` and sequence use; the new
table and sequence are denied to the runtime login after provisioning. The
fixtures also confirm denial of
persistent table DDL, role creation, database creation, `SET ROLE` to the admin,
and connections to `postgres`, `template1`, and another database. A fresh copy
of the populated legacy application database also passed the runtime-role
fixture: selected row counts matched the earlier restore record, the native
`public_locations()` query and a PostGIS function succeeded, and synthetic-table
DML/sequence checks passed. Persistent DDL and connections to the other two
databases on that instance were denied. Public-view rows were queried in memory,
but no row payloads were emitted to logs or changed; Directus/Metabase were not
started in this native-runtime check. A separate consumer-role fixture then
verified those service boundaries; Directus bootstrap/runtime reached healthy,
while Metabase app startup is tracked separately. The repeatable runner is
`docker-compose.kernel-recovery-populated-role.yml`; it attaches to the
internal-only network of the separate recovery project.

The 14 October mobile credential role acceptance verified that direct
`SELECT`, `SELECT *`, and hash predicates cannot read device-token, push, or
enrollment-code credentials; representative last-seen, enrollment issuance,
enrollment revocation and device telemetry SQL continue to work. Device-token
revocation now uses a bounded database function. The actual
runtime login also called the existing bounded token resolver and one-time
enrollment redemption functions successfully. See
[mobile role evidence](builds/2026-10-14-recovery/runtime-mobile-credential-role-disposable.json).
The tenant-preflight inventory no longer queries credential columns and labels
its aggregate count as active unbound devices rather than inferring token
presence. This acceptance did not exercise Gateway handlers through the runtime
login, roll the role out to the candidate, or enable application-table RLS.

Both fixtures ran without published ports or network egress. Their database
containers are stopped and named volumes retained. The current candidate remains
healthy and owner-backed; legacy services remain stopped. No candidate or legacy
application database ACLs or schemas were changed by these checks.

For an app rollback, stop the runtime app/worker and restore the owner credentials
in the Compose environment. The tighter database ACLs persist; keep them in
place unless a reviewed restore plan requires broader access. If reverting
migration 395's callers, the functions and auth role can remain unused. To
abandon the role policy entirely, restore a pre-change database checkpoint
rather than granting broad access without an inventory of affected roles.

Machine evidence: [synthetic role isolation](builds/2026-10-11-recovery/runtime-role-isolation.json),
[populated restore check](builds/2026-10-11-recovery/runtime-role-populated-restore.json),
[optional consumer role boundaries](builds/2026-10-11-recovery/optional-consumer-db-roles.json),
[operator-session role boundary](builds/2026-10-14-recovery/operator-session-role-disposable.json),
[mobile credential role boundary](builds/2026-10-14-recovery/runtime-mobile-credential-role-disposable.json),
[future-object default-deny boundary](builds/2026-10-14-recovery/runtime-role-default-privileges-disposable.json).

## Bounded device revocation and restore ACL repair — 14 October 2026

Migration 398 removes direct runtime UPDATE on device status, token hash, and
revocation time. The `kokonut_mobile_device_revoke_owner` function owner has
only the columns and tenant-context functions it needs, does not log in, and
cannot bypass RLS. `kokonut_security.revoke_mobile_device` revalidates the
exact credential/session, tenant, location, resource, and action before
revoking one active device. The device's token hash is cleared in the same
transaction. Migration 399 grants the runtime role only schema `USAGE` when it
already exists; role bootstrap applies that grant and the bounded function
execute grant for fresh or restored databases.

The exact encrypted checkpoint restore/replay plus forced-RLS synthetic fixture
passed API-key, capability, operator, wrong-action/location, cross-tenant,
direct-column-denial, and transaction-reset checks. The candidate is at
migration 399 with RLS disabled and an anonymous protected-route 401, but still
uses the `kokonut` superuser. Separate runtime credentials and authenticated
HTTP-under-runtime acceptance remain open ([evidence](builds/2026-10-14-recovery/candidate-migration-398-399-device-revocation.json)).

## Database-only restore owner repair — migration 400

A custom database archive omits cluster roles and object-level ACLs. Migration
400 creates or validates six bounded `NOLOGIN`, `NOINHERIT`, non-superuser,
non-bypass function-owner roles; restores their narrow grants; reassigns the
protected `SECURITY DEFINER` functions; restores runtime/operator-auth schema
lookup; and fails if an owner role has unexpected attributes or membership.
`scripts/kernel-restore-role-prerequisites.sql` must run against the target
cluster before `pg_restore`, because restored RLS policies can reference these
role names. It only creates or validates those role names; migration 400
rebuilds database-local grants and ownership.

The restored pre-398 clone replayed migrations 398–400. A populated-clone role
bootstrap did not complete because host Docker-port access failed. Separately,
a private-network synthetic owner/ACL-loss fixture passed the runtime-role
bootstrap, forced-RLS bounded device revocation, and operator authentication
without direct session or identity table reads. Treat that as synthetic
acceptance, not full populated-restore acceptance. The local candidate has
migration 400 applied and retains its age-encrypted pre-400 checkpoint, but the
checkpoint itself has not been restore-rehearsed. Candidate runtime credentials
remain unprovisioned and application-table RLS remains disabled. See the
[migration 400 record](builds/2026-10-14-recovery/candidate-migration-400-restore-owner-repair.json).
