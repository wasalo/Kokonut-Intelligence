# Legacy storage preservation — Batch 2

10 October 2026. The additive scripts/kernel-legacy-archive.py captures volumes
attached to the nine stopped legacy containers and config/, extensions/ and
.env.sops. It uses a pinned helper with read-only mounts and no network, streams
tar directly into age encryption, refuses an existing destination and checks the
container identities, mounts and stopped timestamps again before finalizing.
All named and anonymous attached volumes are mapped in its manifest. No legacy
provider is started. Ruff passed; no acceptance test suite ran.

Set `SOPS_AGE_KEY_FILE` to the operator-controlled private age identity path
before creating the public recipient; do not store or share the identity in the
repository.

```bash
recipient=$(age-keygen -y "$SOPS_AGE_KEY_FILE")
python3 scripts/kernel-legacy-archive.py \
  --destination backups/NEW_LEGACY_CHECKPOINT --recipient "$recipient"
```

The private age identity is intentionally excluded. Preserve it separately using
your key custody procedure. The user selected local development copies for now and deferred independent R2
production backups until implementation finishes. The development mirror lives at
backups/development-mirror/. A same-disk copy does not close the production gate.

## Scope and limitations

PostgreSQL raw files preserve all locally stored databases, including any Metabase
database, and roles. They require the recorded engine and crash recovery; they
do not establish a portable logical backup or successful restoration. ClickHouse
storage/logs, Directus uploads, Metabase files, Redis persistence, broker data/logs
and Caddy state are captured. Configuration contains private certificates and
must remain encrypted. Bind-mounted mobile/maps application source is in the
checkout, not this archive; source changes remain uncommitted and must be retained
separately before any checkout disposal.

Provider-presence.json in builds/2026-10-10-recovery records only boolean settings
presence from encrypted local environment and legacy gateway/Directus plus current
portability API. No Prefect API or mobile S3/local-media settings were present.
These observations do not exclude external deployments, alternate configuration,
or previously uploaded remote objects. Metabase is configured to use PostgreSQL;
its database existence and contents remain unassessed while legacy is stopped.
Redis keys/TTLs and buffered MQTT messages remain logically unassessed.

## Staging restore procedure

1. Match ciphertext size/SHA256 against the archive manifest; decrypt with age.
2. Create a NEW staging volume on a dedicated recovery project. Use the same
   pinned helper to extract there, never onto the preserved original volumes.
3. The archive was generated from fixed /inventory mounts; validate member paths
   and symlink targets before extraction. Reject absolute paths and traversal.
   Keep staging private. Do not extract unreviewed files into the host checkout.
4. Compare staged logical file counts/bytes and archive mappings. Review each
   provider's documented recovery requirements, then copy into new provider-specific
   volumes while preserving permissions/ownership. Never reuse original volumes.
5. Start compatible engine clones with internal networks and no exposed ports,
   disable application/indexer workers, and obtain logical inventories/dumps.
   PostgreSQL/ClickHouse engine compatibility and Redis/MQTT sessions/messages need
   their own retained evidence before provider retirement.
6. Stop recovery services; retain staging volumes and ciphertext. Rollback is the
   unchanged stopped legacy containers, volumes and original configuration.

This procedure is prepared, not executed. File preservation alone does not close
Batch 2 recovery acceptance. Populated durable work/media recovery, logical legacy
inventory, external ownership and independent encrypted storage remain open.

## Remaining volume sizes

Read-only apparent-byte measurements: PostgreSQL 280,614,319; ClickHouse data
1,305,414,640; ClickHouse logs 1,045,332,035; Caddy data 1,904; Caddy config 3,123.
These include directory metadata. Empty application analytics tables observed
earlier do not imply empty ClickHouse storage or logs; both stores are retained.

## Capture completed

The finalized archive is backups/legacy-storage-batch2-20261010/legacy-storage.tar.age
and contains ten attached volumes plus the selected bindings. Aggregate manifest:
[retained mappings](builds/2026-10-10-recovery/legacy-archive-manifest.json).
It does not establish restore success. Original storage/config remain retained.

Development mirror copies completed; every ciphertext and metadata file matched
SHA256. [Comparison](builds/2026-10-10-recovery/development-mirror.json).
