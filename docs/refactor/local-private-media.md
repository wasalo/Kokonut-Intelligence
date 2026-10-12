# Encrypted local private field media

`PrivateMediaStore` in `services/mobile/media_storage.py` describes the existing
upload, metadata-check, cleanup, and private-object inventory contract. S3
remains the default provider.
Explicit `MOBILE_MEDIA_PROVIDER=local` selects `services/mobile/local_media.py`;
unknown providers fail configuration. Local selection requires no S3 settings.

Local configuration requires an absolute dedicated directory owned by the app
with mode 0700 and `MOBILE_MEDIA_LOCAL_KEY`, a random 32-byte key encoded as hex.
Missing/invalid keys fail before directory creation. Keep this key encrypted in
SOPS and inject it into the runtime; it is not generated automatically or logged.
The local driver requires PyCryptodome, now an explicit dependency (previously
already installed transitively by Web3 in the candidate).

Files use AES-256-GCM with fresh random 12-byte nonces and 16-byte authentication
tags. The object key and envelope version are authenticated associated data.
The API follows the library's documented authenticated-encryption methods:
[PyCryptodome GCM](https://www.pycryptodome.org/src/cipher/modern#gcm-mode).
Object filenames are hashes of validated private virtual keys; no user-supplied
path is used as a filesystem path. Writes use private temporary files, fsync,
and exclusive hard-link publication so existing objects are never overwritten.
Reads reject symlinks/non-regular files, bound envelope size, and authenticate
the full object before returning length/type metadata. Deletion is idempotent.

JPEG/type and 2 MB limits remain. Device-token auth, location scoping, upload
hash records, transactional registration, sync verification, and cleanup on
registration rollback stay in the existing mobile API. Files are never mounted
as static assets or given public URLs. This adapter does not add download routes
or bypass existing access checks.

## Adoption and recovery gates

- Prepare a persistent app-owned private directory/volume and inject a distinct
  random encryption key through SOPS; never reuse a database password as the key.
- Validate upload, sync metadata checks, corruption/wrong-key rejection,
  traversal/symlink handling, exclusive-write races, disk failure, and rollback.
- Back up encrypted files and the matching key separately; rehearse recovery
  and verify content hashes against upload records.
- Do not switch an installation containing S3 uploads to local without an
  explicit object migration and reconciliation. The current DB/runtime select
  one provider globally; there is no per-object backend routing or key rotation.
- Recover orphaned temporary/unregistered objects only through reviewed
  reconciliation; crashes between file publication and DB commit can leave them.

Lint, dependency alignment (11 groups / 28 direct requirements), and whitespace
checks passed. Runtime/security and recovery suites remain pending. The isolated
runtime check below generated a one-run synthetic key in a private temporary file
and removed it with the test object. No production key or evidence was created,
and local storage is not enabled in the running candidate. Rebuild before using
this adapter. The old S3 default remains usable.
Rollback removes local selection; preserve files and their key if any local
objects have been written. Do not delete evidence during provider switching.


## Isolated runtime acceptance — 12 October 2026

A synthetic 67-byte JPEG passed the upload route against the restored
`kokonut_restore` clone with `MOBILE_MEDIA_PROVIDER=local` enabled only for a
temporary loopback Gateway process. The local adapter wrote a mode-0600 `KKM1`
AES-256-GCM envelope under a mode-0700 temporary directory. The uploaded bytes
were not present in the file; authenticated `head_private` matched the original
content type and length, and an incorrect key was rejected. Sync verified the
object metadata and attached the media ID to a valid 1.2.0 collection. The row
remained pending and ineligible for downstream use.

All synthetic database rows, encrypted bytes, the ephemeral key, and the
Gateway spool were removed. The candidate's running provider configuration was
unchanged. This does not verify persistence across container replacement,
production media-key recovery through SOPS, database upload-record parity,
expiry/orphan cleanup, or browser offline capture. An isolated one-object archive/restore
rehearsal is documented below. The access contract intentionally defines no
public download endpoint; the client keeps its local photo preview and the
server verifies private objects internally. See
[runtime evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json).


## Isolated age-encrypted backup and restore rehearsal — 12 October 2026

The repository checkpoint and restore scripts were exercised with one synthetic
`KKM1` object from `LocalMediaStore`. The checkpoint tool created an age-encrypted
archive and manifest, bound to the SHA-256 of a synthetic database-checkpoint
file. The restore tool wrote into a new private directory, authenticated the age
archive and verified the ciphertext inventory. `head_private` then authenticated
the restored object with the separate media key; direct test-only decryption
confirmed the synthetic plaintext SHA-256, and a wrong media key was rejected.

The media key was generated in memory and was not placed in the archive or
manifest. The `sops:MOBILE_MEDIA_LOCAL_KEY` value was only a custody label; no
SOPS secret was read. The database file was a synthetic hash-binding fixture,
not a database backup, and no `mobile_media_upload` row was compared. This does
not certify SOPS key recovery, production database/object parity, persistent
volume recovery, container replacement, expiry/orphan cleanup, or backup
retention. All fixture files and temporary keys were removed; the candidate DB
and media-provider configuration were untouched. See
[recovery evidence](builds/2026-10-12-recovery/field-collector-media-backup-restore.json).


## Restore using the supplied SOPS age identity — 12 October 2026

The archive recipient was derived from the user-provided age identity file. The
checkpoint script encrypted one synthetic `KKM1` object; after removing the
source directory, the restore script decrypted the archive with that identity
into a new private directory. The restored ciphertext digest and inventory
matched, `head_private` authenticated the object with a separate temporary media
key, and an incorrect media key failed.

This confirms that the supplied age identity can decrypt an age archive. The
media key and database-checkpoint binding were still synthetic. No `.env.sops`
value or application secret was decrypted, and production media-key custody,
database upload-row parity, persistent-volume/container recovery, and
expiry/orphan cleanup remain open. All temporary files were removed; the
candidate DB and provider configuration were untouched. See
[SOPS age restore evidence](builds/2026-10-12-recovery/field-collector-media-sops-age-restore.json).


The tracked `.env.sops` now contains a user-approved random
`MOBILE_MEDIA_LOCAL_KEY`. Targeted SOPS readback matched the generated key, and
an isolated one-object checkpoint/restore using that exact key and the supplied
age identity passed AES-GCM authentication, plaintext digest, and wrong-key
checks. `MOBILE_MEDIA_PROVIDER` remains unset, so the source and base Compose
profile still default to S3; the candidate was not reconfigured. The edge profile
has the encrypted key available when local media is deliberately selected.
Historical key-availability evidence records the state before provisioning; see
[current provisioning and recovery evidence](builds/2026-10-12-recovery/field-collector-media-sops-key-provisioning.json)
and [historical availability evidence](builds/2026-10-12-recovery/field-collector-media-sops-key-availability.json).

The key-matched rehearsal used a synthetic database-checkpoint binding fixture.
It did not restore PostgreSQL or compare `mobile_media_upload` rows with object
inventory, exercise a persistent Compose volume/container replacement, or test
expiry/orphan cleanup and production retention. Those remain adoption gates.

An isolated `kernel-edge` Compose check subsequently confirmed that the
SOPS-managed key can authenticate an object written to the named media volume by
one disposable app container and recovered by a second. Directory/file modes,
plaintext absence, wrong-key rejection, and synthetic cleanup passed. This did
not involve PostgreSQL or a live candidate service. See [edge volume recovery
evidence](builds/2026-10-12-recovery/field-collector-edge-media-volume-recovery.json).


## Isolated PostgreSQL/object parity — 12 October 2026

Migration 358 was applied in a disposable PostGIS Compose project after creating
minimal synthetic prerequisite tables. One synthetic `mobile_media_upload` row
was registered for a KKM1 object written to the edge profile's named media
volume. The database object key, content type, byte size, and SHA-256 matched the
object metadata. A second disposable app container queried the row, authenticated
the AES-GCM envelope, decrypted it in memory, and confirmed the plaintext
SHA-256 matched the row; an altered media key was rejected. The row, device,
location, object, network, and project volumes were removed.

The SOPS-managed local-media key and database password were read only into
process/container memory for this isolated check. The candidate database and
running app were untouched. This was not an HTTP upload-route test, a full
ordered migration replay, or a candidate service recreation. Expiry/orphan
cleanup and production retention remain open. See [parity evidence](builds/2026-10-12-recovery/field-collector-media-db-object-parity.json).


## Expire unattached uploads

The bounded operator command in `services/mobile/media_cleanup.py` uses the
existing 30-day `expires_at` default from migration 358. It is dry-run by
default and reports only the number of eligible rows. Apply mode is explicit
and accepts a limit from 1 to 500:

```bash
python3 -m services.cli mobile-media-cleanup --limit 100
python3 -m services.cli mobile-media-cleanup --apply --limit 100
```

Only rows still `uploaded`, past expiry, and without an attached collection are
eligible. Apply locks one row with `FOR UPDATE SKIP LOCKED`, deletes its private
object, then marks the row `expired` in the same database transaction. If
provider deletion or the database commit fails, the upload row remains eligible
for retry; provider errors are reported by type without exposing object keys.
Attached photos remain for governed retention/erasure review. This command
does not delete unregistered objects; use the separate reconciliation command
below for aged crash-orphans.

An isolated run applied migration 358 in disposable PostGIS, then exercised a
dry-run, two bounded applies, and a repeat no-op against two expired unattached
objects, one expired attached object, and one live upload. The expired uploads
were deleted and marked expired; the attached and live objects remained. The
eight cleanup unit tests and the broader 44-case mobile/media/API/CLI regression
set passed; standard and security Ruff passed. Synthetic rows, objects, and
project resources were removed. The running candidate was untouched. See
[cleanup evidence](builds/2026-10-12-recovery/field-collector-media-expiry-cleanup.json).


## Reconcile aged unregistered objects

`services/mobile/media_reconcile.py` inventories the provider's private Field
Collector prefix and compares opaque object identities with registered upload
keys from `mobile_media_upload`. Local storage inventories immutable hashed
`.bin` objects and temporary `.upload-*` files; S3-compatible storage uses
paginated ListObjectsV2. Symlinks, unknown local entries, and non-regular files
fail closed. Raw keys and provider handles never appear in command output.

The unified CLI is dry-run by default. Only objects at least 24 hours old can
be selected, and each apply run is bounded to at most 500 deletions (default
100). Apply re-reads database registrations and the provider inventory just
before each deletion to reduce races with an upload that completed after the
initial snapshot. It never changes database rows; normal expiry cleanup remains
responsible for registered unattached uploads. Temporary upload files receive
the same minimum-age protection.

```bash
python3 -m services.cli mobile-media-reconcile
python3 -m services.cli mobile-media-reconcile --older-than-hours 48 --limit 100
python3 -m services.cli mobile-media-reconcile --apply --older-than-hours 48 --limit 100
```

S3-compatible inventory requires `s3:ListBucket` scoped to the
`private/field-collector/` prefix; explicit apply also requires `s3:DeleteObject`
for that prefix. Local storage requires no external permission. Apply creates
no per-object restore journal; configure provider versioning/backups when
recovery of deleted bytes is required. The code has focused
storage/reconciliation/cleanup coverage, and a dry-run against the local
candidate provider reported zero provider objects and zero registered
upload keys without writes. No S3/R2 bucket was listed, and no apply was run.
Production retention ownership and populated external-provider acceptance
remain open. See [dry-run evidence](builds/2026-10-12-recovery/field-collector-media-orphan-reconcile.json).


## Full runtime volume replacement check — 12 October 2026

Two disposable full Kernel runtime containers using the candidate app image
started on the candidate Docker network with local media selected and a unique
named volume. Each reached the health endpoint against the existing candidate
database. A synthetic encrypted object written before startup authenticated and
matched its plaintext digest after each runtime start. The object, containers,
and named volume were removed; the existing candidate services and configuration
were untouched.

This confirms recovery across full runtime container replacement on the
candidate network. It did not restart or reconfigure the primary candidate app,
run background workers, or exercise the upload/sync flow. See [runtime volume
evidence](builds/2026-10-12-recovery/field-collector-media-runtime-volume-recreation.json).


## Candidate edge-provider activation and restart — 12 October 2026

The candidate app was rebuilt from the current checkout and recreated with the
`docker-compose.kernel-edge.yml` overlay alongside its candidate and Metabase
manifests. The encrypted SOPS key was loaded into process/container memory and
was not printed. The old app image is retained as
`kokonut-kernel-candidate-app:pre-edge-media-6ce3c3f`. Only the app was
recreated; the existing PostgreSQL and Metabase containers remained healthy.

The running app reported provider `local`, mounted
`kokonut-kernel-candidate_kernel-private-media` at `/app/private-media`, and
owned the directory as UID/GID 10001 with mode 0700. A synthetic encrypted JPEG
passed write/head/delete; its KKM1 envelope excluded plaintext and used mode
0600. A second synthetic object survived an app restart, authenticated and
decrypted to the expected SHA-256, then was removed. `mobile_media_upload` held
zero rows before and after; no HTTP upload, database row, or S3 migration was
performed. All three candidate services remained healthy.

This confirms local provider activation and app restart persistence on the
linux/amd64 localhost candidate. It does not certify the ARM64 device, full edge
resource limits on PostgreSQL, end-to-end authenticated upload/sync, production
retention, or R2 recovery. The source and base Compose profile still default to
S3; the running candidate currently uses the edge overlay. To roll back, retag
the preserved image as `latest` and recreate only the app with the base and
Metabase manifests. Preserve the private-media volume and key if real objects
are later written. See [activation evidence](builds/2026-10-12-recovery/field-collector-candidate-edge-media-activation.json).
