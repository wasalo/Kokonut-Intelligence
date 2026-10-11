# Canonical sensor producer recovery

The transactional sensor projection path now reads the stored sensor_reading row
and delegates to the shared sensor projection. Outbox source_id/event_key use the
actual reading UUID, unit comes from PostgreSQL sensor_type, and numeric value
comes from stored NUMERIC(12,4). Missing plot remains NULL. Enqueue exceptions
propagate for caller rollback; the transactional path no longer swallows them.

Same sensor/date/time submissions return the existing reading only if value at
canonical four-decimal precision and quality match. Conflicting value/quality
raises instead of silently creating a different analytics projection. This does
not define a correction workflow: reviewed corrections need a separate policy.
Source ingestion metadata may differ on harmless retries; primary reading identity
and measurement remain unchanged.

[Five isolated checks](builds/2026-10-10-recovery/canonical-sensor.json) passed:
real source rollback on injected enqueue failure, source/outbox idempotency,
conflicting reading rejection, PostgreSQL/raw/v3 numeric parity, and source UUID/
unit preservation. Three measurements include rounding 10.12345 to 10.1235;
source average is 20.0411666666666667. Dedicated manual synthetic sensor at Adelphi;
no device enrollment or human verification authority is created.

## Deployment and rollback

Historical sensor producer rows used a payload hash as source_id/event_key and
sensor type as unit. This change applies to newly projected source rows. Before
promotion, inventory and reconcile/drain legacy queued/delivered projections:
blindly regenerating UUID-keyed projections alongside old hash-keyed rows may
insert duplicates under different delivery tokens. Do not rewrite applied records
or mark them succeeded without sink evidence. Preserve both source and target
backups and develop reviewed lineage repair before any populated cutover.

### Retained local snapshot reconciliation

The captured local legacy PostgreSQL clone contains 15 `sensor_reading` rows with
15 distinct reading IDs and zero `clickhouse_outbox` rows. The paired retained
legacy ClickHouse inventory has zero physical rows in its raw
`default.sensor_readings` table (and zero rows across its inventoried row-bearing
tables). Thus this local snapshot has no queued or delivered sensor projection to
re-key or replay beside the canonical UUID-keyed producer. [Sanitized counts and
scope](builds/2026-10-10-recovery/legacy-sensor-lineage.json).

This does not establish whether a remote, external, or unarchived ClickHouse target
contains historical sensor projections. Reconcile such a target from its own
backup and source/sink evidence before promotion; the local result is not a
populated-target cutover approval. Inspection ran only against a stopped,
no-network recovery clone; no sensor values were queried and the clone was stopped
afterward.

Rebuild coordinated source artifacts and use canonical helper/error behavior.
Rollback stops ingestion/delivery first, retains source/outbox and restores reviewed
provider/source selection. Old swallowing/hash-key behavior is not accepted data
integrity. Runtime images remain unchanged; checks used explicit source mounts.
Both fixture roles stopped with data retained.

Open gates: full CSV/HTTP validation and event side effects, concurrent same-reading
submissions, rounding boundaries/negative values, external/populated-target
lineage, source correction policy and long-window sink recovery. These helper
checks do not certify the entire field-ingestion capability. Batch 2 remains active.
