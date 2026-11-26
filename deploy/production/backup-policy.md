# Candidate backup and recovery policy

**Status:** candidate-only defaults and evidence. This is not an approved
production backup schedule, retention policy, or disaster-recovery authorization.
The active gate and evidence are in the
[canonical refactor guide](../../docs/refactor/current-state-and-implementation.md);
the R2 transfer interface is described in
[`backup-object-storage.md`](../../docs/refactor/backup-object-storage.md).

This document replaces the old draft that specified unimplemented volume
archives, Hostinger/Backblaze storage, a fixed 30-day retention period, and a
legacy host cron. Those settings are not current Kokonut Intelligence policy.

## Candidate recovery targets

Wasabi selected the proposed candidate defaults:

- Candidate soak: 24 hours, with `/health` sampled each minute and at least
  99.5% successful probes outside the planned drill.
- Candidate RPO: no greater than 24 hours, backed by an AES-256-CBC/PBKDF2
  encrypted PostgreSQL checkpoint with an authenticated manifest in the private
  `kokonut-backups` R2 bucket. `BACKUP_ENCRYPTION_KEY` is managed in SOPS.
- Candidate service restart: recover within 15 minutes.
- Isolated checkpoint restore: verify healthy within two hours.
- Controlled drill: restart the PostgreSQL service, then restore a checkpoint
  into a new isolated recovery project. Never restore over the serving database.

These are candidate acceptance targets only. Production RPO/RTO, cadence,
retention, availability, and failover targets remain unapproved.

## Current tools and limits

- `scripts/backup.sh` creates a local checkpoint from its selected Compose
  PostgreSQL service and can export ClickHouse tables when enabled. It does not
  archive arbitrary named Docker volumes or Directus uploads. A separate
  `zitadel` PostgreSQL service is not included unless a reviewed capture path
  explicitly selects it.
- `scripts/verify-backup.sh` checks the authenticated manifest, exact file
  inventory, sizes, and hashes. It does not decrypt database archives or prove
  that a restore succeeds.
- `scripts/backup_remote.py` uploads or downloads one checkpoint using the
  bucket-scoped R2 S3 credentials. Upload commits a signed manifest after
  object readback verification. The CLI intentionally has no list, delete,
  prune, or lifecycle operation.
- `scripts/restore.sh` restores into the configured Compose database service.
  Do not aim it at a live or candidate database. Use an explicitly isolated
  project and verify the actual target before any restore operation.

The repository has evidence for one encrypted candidate checkpoint uploaded to
R2, read back and hash-verified, then restored into temporary isolated
PostgreSQL containers. That one-time rehearsal does not establish recurring
backup, complete multi-service capture, or full Coolify application recovery.
See the [canonical G6 status](../../docs/refactor/current-state-and-implementation.md)
for the exact checkpoint and recovery evidence.

## Storage and secret handling

Use only the dedicated `kokonut-backups` bucket and the
`kokonut-kernel-backups` prefix. Never place candidate backups in
`kokonut-production`. The endpoint, bucket, region, prefix, bucket-scoped
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, and `BACKUP_ENCRYPTION_KEY` belong
in SOPS or the approved runtime secret manager. Never put credential values in
this document, a command argument, or chat.

The transfer CLI cannot delete objects. No fixed object expiry or 30-day
retention is approved. Keep automatic pruning and lifecycle expiration off
until owners approve a configurable jurisdiction-aware retention and legal-hold
policy. Preserve the encryption key for every retained checkpoint; rotating it
requires a reviewed re-encryption and restore plan.

## Remaining acceptance before recurring use

1. Restore candidate health and verify the deployed source revision, database
   identities, and per-service secret isolation.
2. Approve a candidate backup cadence and checkpoint inventory covering every
   required database. Define alerting for failed capture, transfer, and
   verification without relying on the database being backed up.
3. Run a fresh capture, upload with `--apply`, readback verification, and
   restore into a new isolated project. Verify both `kokonut_intelligence` and
   `zitadel`, then remove only the newly created disposable recovery resources.
4. Run and document the controlled PostgreSQL restart and complete the
   24-hour soak. Wasabi reviews and signs off the evidence; Codex operates the
   drill so operator and reviewer remain distinct.
5. Keep production storage, full application/volume coverage, retention,
   restoration windows, and production sign-off as separate decisions.

Do not declare G6 complete from the one-time checkpoint. Do not begin the soak
until G4/G5 prerequisites, candidate health, and a successful full recovery
rehearsal are recorded in the canonical guide.
