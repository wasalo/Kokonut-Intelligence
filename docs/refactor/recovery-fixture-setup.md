# Batch 2 — guarded durable-work fixture setup

10 October 2026. Prepared, not started or seeded. Ruff passed for the loader;
the standalone Compose configuration parsed with encrypted secrets. No SQL seed,
fixture, recovery operation or acceptance suite was executed in this slice.

## Dedicated deployment

docker-compose.kernel-recovery-fixture.yml selects the recorded AMD64 database
and Batch 1 application images. Dedicated project/volume/network names prevent
overlaying the preserved deployments. Its network is internal, no ports published.
Only database starts by default. The tools-profile operator is an ephemeral
schema-readiness command; it starts no API, scheduler or event worker. Local media
has its own app-owned volume; a secret key must be supplied before media operations.
The pinned app artifact predates the new host-side recovery scripts; invoke those
from the checkout, not as if they were bundled in that image.

Before starting, confirm that neither fixture volume exists. Keep any prior
volume/data if found and review a separate destination instead of deleting it.

```bash
source scripts/load-secrets.sh
docker compose --env-file /dev/null -p kokonut-kernel-recovery-fixture \
  -f docker-compose.kernel-recovery-fixture.yml up -d database
```

Wait for final initialization/health, not just the temporary initialization server.
Check the target database has no user relations. Restore the scoped portability
archive into this fresh target, using the same age/pg_restore streaming procedure
as recovery-preparation.md. Check ciphertext SHA256 first. Do not load legacy
logical archives or broad seeds here: this fixture requires all current bundled
migrations through 373. No new migration or seed checksum record is manufactured.

## Guarded work loader

scripts/kernel-recovery-fixture.py validates the fixed container's Compose labels,
recorded database image, sole dedicated volume, internal network, lack of public
ports/privileged mode, and absence of other running fixture roles. Every numbered
schema migration/status/checksum must match the checkout. Preflight without writes:

```bash
python3 scripts/kernel-recovery-fixture.py
```

Explicit seed action:

```bash
python3 scripts/kernel-recovery-fixture.py --apply
```

scripts/fixtures/kernel-recovery-work.sql runs as one transaction with bounded
locks/statements and empty-work-table checks. Reapplication fails; no upsert modifies
existing work. It creates one disabled freshness task, one expired running lease,
one completed run in a different window, one processing event, two disabled handlers
with synthetic success/error delivery/history, and one pending dead letter.
These are development snapshot states, not evidence of actual handler effects or
successful job execution. No schedule or handler is enabled. Fixed dates/UUIDs make
the records recognizable; they are not real reviewer identities or source evidence.

The seed is a development input outside schemas/postgres and schemas/seeds; it
does not change ordered/checksummed migration history. SQL remains unexercised.
On an error, retain the private diagnostic and transaction rollback; do not retry
against an occupied fixture without reconciling its state.

## Remaining fixture and acceptance work

Create the reviewed Adelphi device/offline-collection and two media records/objects
described in work-media-recovery.md through a separately scoped loader. This work
seed does not create them or a media encryption key. Keep all roles quiesced during
capture. With verification authorization, complete the paired DB/media restore,
stale-owner and run-window recovery, handler idempotency, operator replay/disposal,
and AES/device/reference checks. Replace synthetic seeded history with actual
controlled effects evidence before declaring durable-work acceptance.

Rollback: no existing deployment changed by preparation. Future fixture changes
stay on the dedicated volumes; stop that project without deleting volumes or
ciphertext. Full Batch 2 acceptance and capability counts remain unchanged.
