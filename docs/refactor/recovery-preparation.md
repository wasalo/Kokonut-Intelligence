# Batch 2 — recovery preparation

Prepared 10 October 2026; updated 22 October 2026. Scoped candidate PostgreSQL
checkpoint/restore rehearsals are recorded below. This is not a complete
platform backup or production recovery acceptance.

## Ownership findings

Stopped legacy containers retain all named volumes. Read-only mounted inspection
measured regular files and logical bytes only, without reading payloads:

| Store | Files | Bytes | Interpretation |
| --- | ---: | ---: | --- |
| Redis anonymous /data | 1 | 311 | Persistence exists; keys, sessions and TTLs remain unassessed |
| Metabase /metabase-data | 0 | 0 | Mounted directory empty; PostgreSQL metabase database remains unassessed |
| Directus uploads | 0 | 0 | Mounted directory empty; does not establish external media absence |
| Mosquitto data | 2 | 250 | Broker files exist; buffered message count remains unassessed |
| Mosquitto anonymous logs | 0 | 0 | Mounted directory empty |

Redis volume: `f7bd99b76ae32ea1203e6d4c4674802b5878b451a323c84088cb853d09042e9f`.
Broker log volume: `37fd1f759248c37b3d3a8bf527836e73f49939c4f5817ecd3be27d5e2b32cd96`.
These anonymous volumes must be included in retention; recreating containers could
lose their attachment. Measurements are not durable-message or session parity evidence.
age and SOPS are installed. No external S3/Prefect endpoint contents were inspected.

## Scoped PostgreSQL checkpoint

Existing backup.sh requires ClickHouse and omits media/broker/Redis volumes. It is
not a complete Kernel checkpoint. The additive kernel-checkpoint.sh uses streaming
pg_dump custom format into authenticated age encryption; no plaintext dump is
written to disk. It requires an explicit public recipient and a new destination,
preserves incomplete directories, and records ciphertext checksum and DB image.
It backs up only kokonut_intelligence, excluding grants/roles and other databases.
Do not describe it as a complete legacy backup or a verified recovery checkpoint.

Example (substitute your public age recipient; never enter a private key here):

```bash
bash scripts/kernel-checkpoint.sh kokonut-kernel-portability-database-1 \
  backups/kernel-YYYYMMDDTHHMMSSZ AGE_PUBLIC_RECIPIENT
```

pg_dump gives a consistent database snapshot but not a coordinated external-media
snapshot. Before a release checkpoint, quiesce authorized writes/workers, capture
every metadata DB including Metabase, global roles securely, uploaded media and
their encryption keys, Redis persistence/session policy, broker state and config.
Source configuration and external bucket manifests need separate encrypted archives.
Retain originals and two independently accessible encrypted copies until isolated
restore and capability acceptance pass; no automatic pruning is provided.

## Isolated restore procedure

docker-compose.kernel-recovery.yml defines a dedicated internal network and new
volume with no API, workers, host ports or vendor services. Its database image must
be the checkpoint's recorded image; AMD64 only at this stage. Validate the manifest
scope, nonempty archive and SHA256 before decryption. The checksum is accidental
corruption evidence; age authentication supplies ciphertext integrity.

1. Load encrypted secrets with scripts/load-secrets.sh. Set
   KOKONUT_RECOVERY_DATABASE_IMAGE to the manifest image identity. Never restore
   into legacy/candidate/portability or an existing recovery volume.
2. Inspect Docker volumes and containers. If kokonut-kernel-recovery_recovery-postgres-data
   already exists, stop: use a separately reviewed destination. Do not delete it.
3. Start only recovery/database using the standalone manifest and explicit project:

   ```bash
   docker compose --env-file /dev/null -p kokonut-kernel-recovery \
     -f docker-compose.kernel-recovery.yml up -d database
   ```

4. Wait for DB health. The recovery healthcheck requires both PID 1 to be the
   final `postgres` process and a TCP readiness response. The PostGIS entrypoint
   starts a temporary server during extension initialization; a plain
   `pg_isready` can report healthy before that server shuts down. Do not restore
   until this healthcheck passes. The delayed-init disposable check confirms it
   stays starting during the temporary phase and becomes healthy only for the
   final server. The PostGIS image installs extension objects into its
   configured `POSTGRES_DB`; do not restore into that initialized database because
   `pg_restore` will correctly reject the pre-existing PostGIS schemas. The
   database-only archive preserves RLS policies but excludes cluster-global
   roles, so install and validate the narrow NOLOGIN role prerequisites in this
   fresh scratch cluster before restoring:

   ```bash
   docker compose --env-file /dev/null -p kokonut-kernel-recovery \
     -f docker-compose.kernel-recovery.yml exec -T database \
     psql -v ON_ERROR_STOP=1 -U kokonut -d postgres \
     < scripts/kernel-restore-role-prerequisites.sql
   ```

   Then create a separate empty database from PostgreSQL's `template0` and
   verify that it has no user tables before restoring:

   ```bash
   docker compose --env-file /dev/null -p kokonut-kernel-recovery \
     -f docker-compose.kernel-recovery.yml exec -T database \
     createdb -U kokonut -T template0 kokonut_restore
   docker compose --env-file /dev/null -p kokonut-kernel-recovery \
     -f docker-compose.kernel-recovery.yml exec -T database \
     psql -U kokonut -d kokonut_restore -Atc \
     "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
   ```

   Do not apply migrations/seeds before restoring; the dump contains them.
5. In a shell with pipefail enabled, decrypt directly into pg_restore. No --clean
   is used: an unexpected occupied database must fail, not be overwritten. The
   restore target may have a different database name because this dump excludes
   database creation metadata.

   ```bash
   set -o pipefail
   age -d -i /Users/gilbertoadon/.config/sops/age/keys.txt \
     backups/CHECKPOINT/postgres.dump.age |
     docker compose --env-file /dev/null -p kokonut-kernel-recovery \
       -f docker-compose.kernel-recovery.yml exec -T database \
       pg_restore -U kokonut -d kokonut_restore --exit-on-error \
         --single-transaction --no-owner --no-privileges
   ```

6. With verification authorization, compare migration IDs/checksums, extensions,
   domain counts, scheduler leases/run windows, events/deliveries/dead letters,
   projection cursors, media references and permissions. Restored leases require
   reviewed restart/replay handling; no worker starts automatically. A restored
   superuser-owned DB does not prove production least-privilege/grant parity.
7. Stop the recovery project without removing its volume; retain failure logs
   privately. Existing deployments and volumes are the rollback path. The
   template0 target avoids collisions from extensions preinstalled by the
   PostGIS image; a failed transactional restore leaves its target unchanged.

## Pilot fixture plan

Use Kokonut Adelphi. Existing broad seed-pilot.sh includes many domains and cannot
be treated as a scoped fixture. Review dependencies of 001_pilot_farm.sql,
002_pilot_operations.sql, 013_pilot_registry_mrv_agents.sql and
109_adelphi_governance_roles.sql before selecting records. Build an explicit minimal
fixture with separate submitter/reviewer identities, one activity, evidence/media,
draft metric and one report; record lifecycle transitions and expected visibility.
Keep all job activation disabled. Never run broad seeds against the preserved legacy
database to prepare parity evidence. Fixture implementation belongs to Batch 3.

## Evidence and remaining gates

Shell syntax passed for kernel-checkpoint.sh. Recovery Compose parsed successfully
with encrypted secrets; no resolved secrets printed. Five volume aggregates were
measured using a temporary no-network read-only helper, subsequently removed.
Batch 2 remains open: logical provider inventory, complete archives, external media
ownership, and populated runtime/provider recovery are still required. The earlier
preparation slice made no deployment or data changes.

### Batch 2 scoped recovery performed — 10 October 2026

Portability PostgreSQL encrypted checkpoint restored successfully into a fresh,
isolated database. All 364 migration fingerprints, extension versions and eight
selected aggregate counts match. Selected workload/media tables are empty; active
work and media recovery remain unproven. Stopped legacy Redis/broker files archived
with age encryption; logical session/message inventory and archive restore pending.
Recovery container stopped with volume retained; source deployments unchanged.
[Retained evidence](builds/2026-10-10-recovery/README.md). No acceptance suites run. Batch 2 stays open
for complete provider ownership, independent backup copy and populated recovery.

### Candidate pre-400 database restore and role rehearsal — 14 October 2026

The exact encrypted pre-400 candidate database archive was authenticated and
restored into a new internal-only PostgreSQL 16.4/PostGIS 3.4 `template0`
clone. Migration 400 was the only pending schema source; it replayed through
the ordered runner and the follow-up plan had zero pending migrations. The
runtime/operator-auth role bootstrap passed against this restored database
copy. The archive restored 1,010 public tables but contained zero public
location rows; this closes database/role recovery for this checkpoint and does
not prove farm-data parity or complete legacy/provider recovery. The database
container is stopped and its recovery volume retained. See the
[candidate restore evidence](builds/2026-10-14-recovery/candidate-pre400-restore-runtime-role-acceptance.json).

### Candidate migration 403 checkpoint, restore, and rollout — 16 October 2026

A fresh age-encrypted checkpoint of the candidate PostgreSQL database was
authenticated and restored to a new internal-only PostgreSQL 16.4/PostGIS 3.4
`template0` database. The restored clone matched the candidate's 393 schema
ledger rows/checksum fingerprint, extension list, and 1,392 public relations.
The recovery service healthcheck was hardened after the first restore attempt
exposed a readiness race: the PostGIS entrypoint's temporary initialization
server can answer `pg_isready` before its handoff. A disposable delayed-init
check verifies the healthcheck rejects that phase and passes after PID 1 becomes
the final PostgreSQL server.

After the successful restore rehearsal, the ordered runner applied only
`schema:403_kgp_governance_target_policy_projection.sql` to the candidate. The
candidate now records 394 applied schema migrations with zero pending; the
policy table is empty, application-table RLS remains disabled, `/health` returns
200, and the anonymous mobile review queue returns 401. The app, proxy, and
Metabase were not recreated, the legacy stack was untouched, and no seed or
application rows were written. The recovery container is stopped and its volume
retained. This database-only rehearsal does not establish data/media/provider or
production recovery parity. See the [rollout evidence](builds/2026-10-16-recovery/candidate-migration-403-kgp-governance-target-rollout.json).

### Candidate migrations 445–548 checkpoint, restore, and rollout — 22 October 2026

A fresh age-encrypted checkpoint of the local candidate database was authenticated
and restored into a new internal-only PostgreSQL project and empty `template0`
database. The checkpoint contained 435 applied schema migrations through 444,
1,403 public relations, and 1,024 public tables. Migration checksums, extensions,
relations, and exact row counts for 1,023 tables matched. The live candidate's
append-only `access_audit_log` advanced by 10 rows after the snapshot and was
excluded from the live row-count comparison; its restored snapshot had 34,347
rows versus 34,357 on the candidate at verification.

The first restored-clone replay exposed missing NOLOGIN role placeholders in the
recovery prerequisites. The inventory regression now requires the bootstrap to
cover every explicitly granted or owned migration role, and the bootstrap
includes the new source and capability roles with login and privilege escalation
disabled. Its focused tests pass (2). The ordered migration runner then applied
all 104 pending schema migrations, 445–548, to the restored clone and candidate
with zero failures. Both ledgers now contain 539 schema migrations through 548
with matching checksum fingerprint `72b81ae1cc0eee54864726403135553e`; both
report zero pending migrations. No seeds were selected or applied.

Only the candidate `app` image was rebuilt and recreated. It is healthy;
`/health` returns 200 and the anonymous operator mobile review queue returns 401.
The candidate PostgreSQL container and persistent volume remained in place
while its schema was migrated; Metabase, proxy, and legacy stack were not
modified. The recovery container is stopped and its volume retained. The
encrypted checkpoint and complete evidence are recorded
in [the rollout record](builds/2026-10-22-recovery/candidate-migrations-445-548-rollout.json).

This checkpoint covers one PostgreSQL database only; it excludes cluster roles
and grants, other databases, external media/providers, and host-loss recovery.
It remains on the same host disk as the repository. Independent off-host copy,
R2 backup/restore, provider recovery, Raspberry Pi hardware acceptance, and
production/cutover acceptance remain open.


### Candidate migration 551 checkpoint, restore, and rollout — 22 October 2026

A fresh age-encrypted PostgreSQL checkpoint of the local candidate was
authenticated and restored into an internal-only PostgreSQL 16 clone created
from `template0`. The pre-migration schema ledger fingerprint matched the
candidate at 541 entries through migration 550. Migration 551 was applied to the
clone and candidate through the ordered checksummed runner; both now record 542
schema migrations through 551 and zero pending. No seed or farm records were
written. The candidate app alone was rebuilt and recreated, then passed its
in-container health request; candidate PostgreSQL, Metabase, proxy, and the
legacy stack were not recreated. The previous app image is retained under
`kokonut-kernel-candidate-app:rollback-pre-551-20261022`. The restored database
container is stopped while its volume is retained.

The checkpoint covers only the Kokonut database and remains on the same host; it
excludes roles/grants, other databases, and external media. The restored clone
and candidate contain no location rows, so this rehearsal does not establish
populated ecological-data parity. Browser-origin acceptance, production OIDC and
worker credentials, off-host backup/restore, and physical Raspberry Pi behavior
remain open. See the [migration 551 rollout record](builds/2026-10-22-recovery/candidate-migration-551-rollout.json).

A separate current-source ARM64/QEMU schema-only replay applied all 542 ordered
schema files through migration 551 with zero pending or failed entries, no
seeds, and `pg_stat_statements` not readable by `PUBLIC`. It ran in a temporary
Compose project with networking disabled and no host ports; container and
volume cleanup completed. Candidate and legacy services were not touched. This
provides emulated migration compatibility evidence only; it does not test
candidate data or physical Raspberry Pi/power behavior ([replay evidence](builds/2026-10-22-recovery/arm64-qemu-current-schema-551.json)).
