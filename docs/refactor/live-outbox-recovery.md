# Live outbox delivery and bounded replay

Ingestion now explicitly selects CH_DB (including the JSON HTTP compatibility
path). Durable delivery uses clickhouse-connect `raw_insert` with JSONEachRow,
validated identifiers and row width, best-effort date-time parsing, and a stable
SHA256 event-key insertion token. Sensor projection stores absent plot UUID as
NULL; older empty plot UUID payloads are normalized during delivery.

Schema 009 enables a 10,000-block non-replicated deduplication window on the eight
raw event tables. This is bounded retry protection, not permanent event uniqueness.
Expired-window or ambiguous manual replay requires source/sink reconciliation;
never describe this as exactly-once delivery. The delivery token assumes one
immutable event-key projection; conflicting enqueue attempts now fail explicitly.

## Observed dependent-view failure

The real crash-after-insert/before-ack check first retained 3 raw sensor readings
but counted 4 in the v2 materialized summary. Enabling dependent-view deduplication
also failed for this pinned version. Altering a MaterializedView's settings was
rejected. Those failed slices are retained, not repaired or promoted.
[Failure evidence](builds/2026-10-10-recovery/live-outbox-dependent-view-failure.json).

Schema 010 adds finalized **v_daily_sensor_summary_v3** and
**v_sensor_reading_rate_v3** directly over raw rows. These replace v2 as the preferred
sensor read interfaces for replay-safe recovery within the source window. They
have the same scalar fields, require no backfill, and incur raw query cost.
V2 targets remain for historical review; do not adopt them for replayed workloads.
Other legacy materialized rollups also require deliberate raw/accepted interfaces.

## Completed isolated scope

A fresh private analytics companion with no published ports uses the retained
PostgreSQL recovery fixture. Live clickhouse-connect delivered timestamp strings,
nullable UUIDs and sensor metadata to kokonut_analytics. Three PostgreSQL outbox
payloads (10,20,30) produced three raw rows after deterministic insertion-before-
ack failure/reclaim/replay. V3 count/average/min/max match PostgreSQL payload
aggregates; average 20. Succeeded rows were not reclaimed. This is payload parity,
not proof of canonical domain ingestion or all source tables.
[Results and image/source identity](builds/2026-10-10-recovery/live-outbox.json).

Both fixture database and analytics roles are stopped afterward; volumes and
failed/successful slices retained. Source changed after the optional-driver image
build; final checks used an explicit read-only source mount. Rebuild and certify
release images before promotion. No candidate/legacy deployment changed.

## Adoption, rollback and remaining gates

Apply schemas 009/010 in the selected optional target; deploy coordinated new
source; switch reviewed sensor consumers to v3. Preserve raw data and old views.
Rollback stops delivery and restores reviewed source/provider selection; retain
outbox/audit state. Never discard failed rows or reset counters to hide ambiguity.
Measure raw-view cost and block-window retention under workload; exercise restart,
concurrent producers, window eviction, batched inserts and other payload types.
Review saved Metabase queries before claiming dashboard parity. Private fixture
Compose companion is a rehearsal tool, not a default deployment profile.
