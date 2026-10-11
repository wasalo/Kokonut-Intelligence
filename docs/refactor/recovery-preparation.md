# Batch 2 — recovery preparation

10 October 2026. Preparation in progress; no backup or restore rehearsal performed.

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

## Isolated restore procedure (prepared, not executed)

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

4. Wait for DB health. Confirm there are no user relations in public and no custom
   schemas. Do not apply migrations/seeds before restoring; the dump contains them.
5. In a shell with pipefail enabled, decrypt directly into pg_restore. No --clean
   is used: an unexpected occupied database must fail, not be overwritten.

   ```bash
   set -o pipefail
   age -d -i /Users/gilbertoadon/.config/sops/age/keys.txt \
     backups/CHECKPOINT/postgres.dump.age |
     docker compose --env-file /dev/null -p kokonut-kernel-recovery \
       -f docker-compose.kernel-recovery.yml exec -T database \
       pg_restore -U kokonut -d kokonut_intelligence --exit-on-error \
         --single-transaction --no-owner --no-privileges
   ```

6. With verification authorization, compare migration IDs/checksums, extensions,
   domain counts, scheduler leases/run windows, events/deliveries/dead letters,
   projection cursors, media references and permissions. Restored leases require
   reviewed restart/replay handling; no worker starts automatically. A restored
   superuser-owned DB does not prove production least-privilege/grant parity.
7. Stop the recovery project without removing its volume; retain failure logs
   privately. Existing deployments and volumes are the rollback path.

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
No test suites, checkpoint creation, provider startup or restore were performed.
Batch 2 remains open: logical provider inventory, complete archives, external media
ownership and isolated restore evidence are still required. Rollback: no deployment
or data changes were made by this preparation slice.

### Batch 2 scoped recovery performed — 10 October 2026

Portability PostgreSQL encrypted checkpoint restored successfully into a fresh,
isolated database. All 364 migration fingerprints, extension versions and eight
selected aggregate counts match. Selected workload/media tables are empty; active
work and media recovery remain unproven. Stopped legacy Redis/broker files archived
with age encryption; logical session/message inventory and archive restore pending.
Recovery container stopped with volume retained; source deployments unchanged.
[Retained evidence](builds/2026-10-10-recovery/README.md). No acceptance suites run. Batch 2 stays open
for complete provider ownership, independent backup copy and populated recovery.
