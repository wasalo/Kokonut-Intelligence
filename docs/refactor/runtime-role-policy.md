# PostgreSQL runtime-role policy

Status: an opt-in application role and bootstrap command are implemented; the
synthetic and populated-restore checks passed. Separate Directus, Metabase
metadata, and analytics-source role boundaries also passed on isolated
populated copies. The pinned Directus owner bootstrap and DML-only runtime
started successfully. No live candidate, portability, or legacy database was
modified. Metabase dashboard/source parity and full domain-workflow acceptance
remain open; see [optional consumer roles](optional-database-roles.md).

## Role boundary

`POSTGRES_PASSWORD` remains the migration/operator credential for the database
owner. Application code now reads `PG_PASSWORD` first and falls back to
`POSTGRES_PASSWORD` for existing deployments. The candidate can use the
dedicated `KOKONUT_RUNTIME_USER` and `KOKONUT_RUNTIME_PASSWORD` variables when
combined with `docker-compose.kernel-runtime-role.yml`; the app receives only
`PG_USER` and `PG_PASSWORD`, while the one-shot bootstrap receives the admin
credential.

The bootstrap requires a dedicated Kernel PostgreSQL instance and a distinct
runtime password of at least 24 characters. It creates or normalizes the runtime
role as `LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
NOBYPASSRLS`. It refuses to reuse a role that owns database objects. It removes
runtime-role memberships, revokes `PUBLIC CONNECT` on connectable databases,
revokes `CREATE` on the `public` schema, then grants the runtime role `CONNECT`
to the selected database, `USAGE` on `public`, DML on existing public tables,
sequence use, and matching default DML/sequence grants for objects created by
the migration/operator role.

The DML grant spans all public tables. It only removes PostgreSQL owner/admin
powers; it does not replace gateway authorization, row/field controls, or
service-specific review rules. Other services that share this dedicated
database need separately reviewed grants. Do not run this bootstrap against the
legacy stack or a database shared with unrelated applications.

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

Add `KOKONUT_RUNTIME_USER` and a distinct `KOKONUT_RUNTIME_PASSWORD` to the
encrypted secrets file. Keep the host migration environment on the owner
identity (`PG_USER=kokonut`, with `POSTGRES_PASSWORD`); do not set the runtime
password as the migration CLI's `PG_PASSWORD`.

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
second table created after provisioning. They provision twice, verify
`SELECT`/`INSERT`/`UPDATE`/`DELETE` and sequence use, and confirm denial of
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

Both fixtures ran without published ports or network egress. Their database
containers are stopped and named volumes retained. The current candidate remains
healthy and owner-backed; legacy services remain stopped. No candidate or legacy
application database ACLs or schemas were changed by these checks.

For an app rollback, stop the runtime app/worker and restore the owner credentials
in the Compose environment. The tighter database ACLs persist; keep them in
place unless a reviewed restore plan requires broader access. To abandon the
role policy entirely, restore a pre-change database checkpoint rather than
granting broad access without an inventory of affected roles.

Machine evidence: [synthetic role isolation](builds/2026-10-11-recovery/runtime-role-isolation.json),
[populated restore check](builds/2026-10-11-recovery/runtime-role-populated-restore.json),
[optional consumer role boundaries](builds/2026-10-11-recovery/optional-consumer-db-roles.json).
