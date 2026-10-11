# Batch 2 — device/media fixture loader

10 October 2026. Prepared, not executed. Ruff passed for the shared target guard
and both work/media loaders. No fixture records, media uploads, tokens or encryption
keys were created. No SQL seed or acceptance suite was run in this slice.

## Loader inputs and checks

scripts/kernel-recovery-media.py shares the project/image/volume/network and full
migration-checksum guard with kernel-recovery-fixture.py through
scripts/kernel_recovery_guard.py. Only the dedicated fixture database may be
targeted; other fixture roles must be stopped. Database writes use one transaction,
bounded locks and empty location/device/collection/media-table checks. Reapplication
fails rather than modifying prior records. Numbered migrations/seeds are unchanged.

Supply an owner-controlled absolute 0700 directory holding existing encrypted
LocalMediaStore objects, plus a JSON list of exactly these two record identities:

| State | media_id | collection client identity |
| --- | --- | --- |
| uploaded | f0000000-0000-4000-8000-000000000011 | kernel-recovery-upload-client |
| attached | f0000000-0000-4000-8000-000000000012 | kernel-recovery-attached-client |

Device ID: kernel-recovery-adelphi-device. Location ID:
a0000000-0000-0000-0000-000000000001 (Kokonut Adelphi). Each JSON record contains
media_id, status, object_key, size_bytes and content_sha256. Derive object_key using
the existing mobile upload convention: private/field-collector/{location_id}/
{first 20 hex characters of SHA256(device_id)}/{media_id without hyphens}.jpg.
File basename is SHA256(object_key) + .bin, as LocalMediaStore stores it.

Create objects with LocalMediaStore.put_private using a non-private sample JPEG;
record the JPEG byte count and SHA256, not its encrypted-envelope size/hash. Supply
the original MOBILE_MEDIA_LOCAL_KEY through private environment custody. The loader
does not generate or print keys and does not accept a key on the command line.
Use an environment where the storage dependency group/PyCryptodome is installed.

Each file must be a private regular owner-controlled file. Symlinks and oversized
envelopes fail. The loader checks the exact farm/device/media object key, performs
AES-GCM authentication with that object key as associated data, checks the JPEG
signature, and recomputes plaintext size/hash. No plaintext/image/key is printed or
written by this loader. Supplied metadata cannot substitute another object/scope.

```bash
.venv/bin/python scripts/kernel-recovery-media.py \
  --records /PRIVATE/fixture-media-records.json \
  --directory /ABSOLUTE/PRIVATE_FIXTURE_MEDIA
# Same inputs with --apply insert the synthetic snapshot records.
```

Default invocation authenticates inputs and checks target/schema but does not
insert records. An explicit --apply inserts one Adelphi location, one synthetic
device, one offline collection and uploaded/attached media rows. The SQL is
scripts/fixtures/kernel-recovery-media.sql. Metadata is passed through psql variable
quoting, not interpolated into SQL. Extra input fields grant no authority.

## Scope of the synthetic device

The seeded device has no device_token_hash and no trusted enrollment. No human
reviewer, consent or bearer authority is fabricated. Collection sync_status and
media attachment state are synthetic recovery snapshot data, not proof that live
capture/sync ran successfully. Enrollment/authentication/tenant consent require
their own real governed flow and acceptance evidence.

## Storage placement and recovery

The loader reads the supplied owner-controlled directory and registers references;
it does not copy those files into the Compose media volume. Keep that directory as
the fixture's actual media source for the paired database/media checkpoint. The
Compose fixture-private-media volume remains unused until objects are explicitly
restored/copied there with correct owner/mode. Do not start an app against an empty
volume and claim that references resolve.

Follow work-media-recovery.md to quiesce, bind DB/media checkpoints, mirror
ciphertext, restore into fresh targets and authenticate the resulting references
with the original key. Execution and failure-path checks remain open. Rollback:
all changes confined to dedicated fixture DB and private media paths; retained
original stacks/archives unchanged. No complete capability/phase gate closes from
this prepared loader. Independent R2 production backups remain deferred.
