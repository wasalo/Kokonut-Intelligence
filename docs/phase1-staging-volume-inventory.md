# KI Staging retained-volume inventory

**Evidence date:** 2026-10-01
**Status:** Read-only inventory; no data disposition decision.

## Scope and method

Inspected Docker volumes carrying the `com.docker.compose.project=ki-staging` label on `cerberus`. Compared logical volume names with `/opt/ki-staging/docker-compose.yml`, recorded `du -sb` apparent bytes for each volume data directory, and checked for any container references with `docker ps -a --filter volume=<volume>`. A project-label container query also returned none.

No files inside the eight retained volume trees, database rows, or plaintext environment values were inspected. The separate backup log and manifest metadata were read. A non-disclosing SOPS check later used the existing age key and redirected all plaintext output to `/dev/null`; key material and plaintext values were not displayed or persisted by the agent. No containers were started, and no retained volume was mounted for inspection. The initial inventory made no host state change; after separate user approval, a mode/group-only repair to `.env.sops` was applied as recorded below. No backup, snapshot, archive, volume deletion, or restore was performed.

## Observed volumes

| Compose volume | Docker volume | Apparent bytes (`du -sb`) | Service/content classification from Compose | Data-origin classification |
|---|---|---:|---|---|
| `postgres-data` | `ki-staging_postgres-data` | 321,388,279 | PostgreSQL/PostGIS persistent database directory | **Unknown.** The repository records that migrations and seeds were applied, but this inventory does not establish whether the retained database also contains manual, historical, or other non-seed records. Treat as potentially sensitive and non-disposable. |
| `directus-uploads` | `ki-staging_directus-uploads` | 0 | Directus upload storage | No files observed by size; contents not opened. Do not infer that related files are absent from bind mounts or backups. |
| `metabase-data` | `ki-staging_metabase-data` | 0 | Metabase persistent application data | No files observed by size; contents not opened. |
| `clickhouse-data` | `ki-staging_clickhouse-data` | 2,645,096,569 | ClickHouse persistent analytics data | **Unknown.** Data origin and whether records are entirely seeded were not assessed. Treat as potentially sensitive and non-disposable. |
| `clickhouse-logs` | `ki-staging_clickhouse-logs` | 448,920,898 | ClickHouse server log storage | Log contents not opened or classified. Retain pending an approved retention decision. |
| `caddy-data` | `ki-staging_caddy-data` | 143 | Caddy persistent runtime data | Non-empty; contents not opened or classified. |
| `caddy-config` | `ki-staging_caddy-config` | 3,123 | Caddy persistent configuration storage | Non-empty; contents not opened or classified. |
| `mosquitto-data` | `ki-staging_mosquitto-data` | 245 | Mosquitto persistent broker data | Non-empty; contents not opened or classified. |

All eight are local-driver Docker volumes labeled for Compose project `ki-staging`, created at `2026-08-21T07:20:41Z`. No container references were found for any of the eight, and no containers labeled as members of Compose project `ki-staging` were present.

The byte counts are apparent sizes of the volume data directories at capture time, not backup sizes or a measurement of recoverability. Docker/Compose labels and the repository Compose file identify service roles; they do not identify the actual records or their provenance.

## Backup state observed (metadata and logs only)

A read-only listing under `/opt/ki-staging/backups` found one checkpoint directory: `staging-20260821T181351Z`, with manifest timestamp `2026-08-21T18:13:56.563686Z`. The manifest lists an encrypted PostgreSQL dump (4,923,072 bytes) and an encrypted ClickHouse schema file (32 bytes); it lists no ClickHouse table-data exports or copies of the other named volumes. The recorded SHA-256 values for both encrypted artifacts were recomputed and matched the manifest. This verifies file-level integrity only, not decryption or recovery.

The host backup log records an SOPS recipient/identity mismatch on 2026-08-22, then repeated failures to open `/opt/ki-staging/.env.sops` from 2026-08-23 through 2026-10-01. The `ubuntu` user crontab runs the backup at 03:30; before repair, `.env.sops` was `0600 root:root` while `.age-key` was `0600 ubuntu:ubuntu`. That ownership/mode mismatch explains the later permission-denied failures; the earlier recipient mismatch is a separate historical error. After Wasabi authorized backup-job repair, on 2026-10-01 the encrypted file was changed to `0640 root:ubuntu`, preserving root ownership and granting read-only access to the age-key/cron group. Its SHA-256 was unchanged. A non-disclosing SOPS decryption test with the same flags as `scripts/load-secrets.sh` succeeded as `ubuntu`, with stdout/stderr discarded. No key material or plaintext values were displayed or persisted; the key file and cron entry were not changed.

The inspected `verify-backup.sh` checks that manifest-listed files exist, are non-empty, and match SHA-256. It does not decrypt or restore them. The only visible checkpoint predates the logged failures, and neither its decryptability nor a restore rehearsal is established. It is not evidence of a full backup of the retained volumes.

## Gate status and follow-up

This completes only the non-invasive name, service-role, size, container-reference, backup-file, and backup-log inventory. The immediate `.env.sops` access blocker is corrected on the live host and covered by an uncommitted deploy-script change, but no new checkpoint was generated. The Staging database and ClickHouse services are absent, so the backup script cannot be exercised without a separately approved service start or alternate snapshot procedure. No current decrypt-and-restore-verified backup is established. Seed-versus-manual/historical provenance remains open for `postgres-data` and `clickhouse-data`; logs and the smaller non-empty service volumes also remain unclassified.

Before any archive or disposition decision:

1. Merge/deploy the uncommitted permission-handling fix in `deploy/scripts/` through the approved workflow so a future host rewrap does not restore the `0600 root:root` failure. The live file is currently `0640 root:ubuntu`.
2. Before generating or validating a complete checkpoint, obtain separate approval for a safe procedure: the current backup script requires running PostgreSQL and ClickHouse, and no services were started under this authorization. Then verify decryption and restore in an isolated target.
3. Have the data owner authorize a bounded, read-only classification method for the database and analytics volumes. Do not start services against the retained originals without a separately reviewed procedure.
4. Record explicit owner approval for any archive or deletion. **Do not prune or delete any of these volumes based on size or emptiness alone.**

Automatic Staging deployment remains outside this inventory and unchanged. No Cloudflare resources, DNS, CI triggers, or production state were changed.
