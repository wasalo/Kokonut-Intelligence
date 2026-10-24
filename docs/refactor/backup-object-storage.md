# Encrypted checkpoint object-storage transport

Status: local transfer tooling is implemented; no live R2 credentials or
objects have been used. This prepares an independent-copy path but does not
close populated recovery, production backup, retention, or cutover acceptance.

## Configuration

Use the dedicated `kokonut-backups` bucket. The owner supplied the R2 S3 API
endpoint for account `7219a605e3c2144a30987e20fd4cf397`:
`https://7219a605e3c2144a30987e20fd4cf397.r2.cloudflarestorage.com`.
Do not use the `kokonut-production` bucket for database checkpoints.

Provision these settings through SOPS or the production secret manager. Never
put credentials in this document, a command argument, or chat:

```dotenv
KOKONUT_BACKUP_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
KOKONUT_BACKUP_S3_BUCKET=kokonut-backups
KOKONUT_BACKUP_S3_REGION=auto
KOKONUT_BACKUP_S3_PREFIX=kokonut-kernel-backups
AWS_ACCESS_KEY_ID=<dedicated bucket-scoped token access key>
AWS_SECRET_ACCESS_KEY=<dedicated bucket-scoped token secret>
BACKUP_ENCRYPTION_KEY=<existing checkpoint encryption key>
```

The remote token should be scoped to read and write only in the backup bucket;
the transfer CLI has no delete operation. The `AWS_*` variables are consumed
only by the optional transfer CLI. Boto3 is already in the repository's runtime
dependency groups. The remote operation remains unavailable until credentials
are provisioned separately.

## Commands

Create and locally verify an encrypted checkpoint as usual, then preview the
transfer. `--apply` is required for either remote upload or local download:

```sh
source scripts/load-secrets.sh
scripts/backup.sh --backup-id checkpoint-20261015T120000Z
python3 scripts/backup_remote.py upload backups/checkpoint-20261015T120000Z
python3 scripts/backup_remote.py upload backups/checkpoint-20261015T120000Z --apply
python3 scripts/backup_remote.py download checkpoint-20261015T120000Z --destination /secure/restore-staging
python3 scripts/backup_remote.py download checkpoint-20261015T120000Z --destination /secure/restore-staging --apply
```

Downloads are written to a new private directory named after the backup ID;
existing destinations are never overwritten. The restored checkpoint is
verified before the directory is made visible. Use `scripts/restore.sh` only
after a separate target review, restore preflight, and approved isolated
rehearsal.

## Integrity and recovery behavior

- Newly created checkpoint manifests are authenticated with HMAC-SHA-256. The
  signing key is derived from `BACKUP_ENCRYPTION_KEY` with a per-manifest random
  salt and PBKDF2-HMAC-SHA-256. This authenticates the manifest and artifact
  digests; the existing encrypted artifact format remains unchanged.
- Unsigned legacy checkpoints remain locally verifiable for compatibility, but
  remote upload requires an authenticated manifest. Recreate an unsigned
  checkpoint before uploading it.
- Artifact bytes are uploaded beneath a unique staging prefix and read back for
  SHA-256 and length verification. A conditional, create-only `manifest.json`
  marker is committed last. A backup ID cannot be rebound to different
  checkpoint contents. An interrupted upload leaves uncommitted staged objects
  that are not treated as a completed backup; the CLI deliberately does not
  delete them.
- Download validates the signed marker, exact artifact inventory, each object
  hash and size, and the regular local checkpoint verifier before atomically
  publishing a new private directory.
- There is no remote list, prune, delete, lifecycle, or legal-hold action in
  this CLI. R2 object inventory, production restore rehearsal, a dynamic
  retention/lifecycle policy, and disposition of orphan staging objects remain
  separate operational gates. Do not configure a fixed object-expiry period.

Rollback: stop using the optional transport command. Existing local checkpoints
and remote objects are left unchanged. A failed remote transfer has no committed
manifest marker; an operator can inspect its unique prefix later under the
approved storage policy.

Source evidence: `tests/test_backup_remote.py` and
`tests/test_backup_optional_providers.py`. These use local fixtures and a fake
S3 client; they do not contact Cloudflare or prove production restore.
