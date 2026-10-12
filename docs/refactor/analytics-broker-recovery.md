# Batch 2 — ClickHouse and offline broker inventory

10 October 2026. Original legacy providers stayed stopped. No application workers,
indexers, sensor publications or production cutover were enabled.

## ClickHouse recovered storage

Stopped ClickHouse files were copied through a read-only source mount into new
volume kokonut-kernel-recovery-clickhouse. The compatible pinned engine ran with
network mode none, no host ports, two CPUs and a 2 GB memory limit. Version:
25.8.28.1. Image: sha256:a9d328123ff8a61bf6b16448528b577d59deb85758172e13b09054b0727f8adf.
The clone is stopped; volume retained. Original data/log volumes are unchanged.

The expected kokonut_analytics database has no tables. **default has 34 objects:**

| Engine | Objects | Reported physical rows |
| --- | ---: | ---: |
| MergeTree | 8 | 0 |
| SummingMergeTree | 9 | 0 |
| AggregatingMergeTree | 2 | 0 |
| MaterializedView | 11 | 0 |
| View | 4 | Not physical storage |

No active non-system parts were returned by system.parts. These observations
correct the earlier scoped inventory; an empty kokonut_analytics database never
established absence of analytics objects elsewhere. System storage/history and
logs remain in the encrypted raw archive. No private historical queries were read.

All 34 create_table_query definitions captured as encrypted JSONL metadata under
backups/clickhouse-metadata-batch2-20261010/, with matching ciphertext in the local
development mirror. This is not an ordered executable restore script; dependencies,
UUID-based materialized inner tables and target database mapping require explicit
handling. No populated analytics dataset exists here to certify output parity.

[Complete object inventory](builds/2026-10-10-recovery/clickhouse-application-inventory.jsonl)
and [encrypted metadata archive record](builds/2026-10-10-recovery/clickhouse-metadata-manifest.json).
Phase 3 must reconcile actual object database ownership against client CH_DB and
schemas/clickhouse/001–006 before cutover. Do not drop, move or recreate legacy
objects merely because the configured expected database is empty.

## Original broker persistence framing

Added scripts/kernel-broker-inventory.py: a bounded stdlib scanner for Mosquitto
version 6 framing. It checks magic/version, known chunk IDs, lengths and file bounds,
requires one configuration record, and skips private payload/client/topic records.
Unsupported/truncated framing fails. It does not validate payloads or references.
The supported file size ceiling is 64 MB; no silent partial inventory is returned.

Format references: upstream [persistence definitions](https://raw.githubusercontent.com/eclipse-mosquitto/mosquitto/v2.0.22/src/persist.h),
[header reader](https://raw.githubusercontent.com/eclipse-mosquitto/mosquitto/v2.0.22/src/persist_read_v5.c)
and [file reader](https://raw.githubusercontent.com/eclipse-mosquitto/mosquitto/v2.0.22/src/persist_read.c).
No upstream source was copied into the repository.

Executed on the ORIGINAL stopped volume through a read-only mount, not the
previous clone's shutdown-written persistence. The 47-byte version 6 file contains
one configuration chunk and zero message-store, client-message, retained-reference,
subscription or client chunks. [Exact snapshot fingerprint/counts](builds/2026-10-10-recovery/broker-offline-inventory.json).
This closes original persisted chunk inventory. Previous live SYS counters remain
anomalous and are superseded for this purpose. In-memory state before shutdown,
delivery/reconnect semantics and human operator replay remain unassessed.

## Acceptance and rollback

Ruff passed for the scanner; no acceptance test suites ran. ClickHouse source file
copy successfully loaded in a compatible engine; encrypted SQL-definition restore
and analytics output parity remain open. Broker framing count does not certify
transport authorization, message semantics or outage recovery. Active work/private
media recovery, permissions, Redis semantic ownership and external configuration
reconciliation remain Batch 2 gaps. Independent R2 backups are deferred by user
instruction. Retained original volumes/ciphertext are rollback sources; do not
replace or delete them. Running Kernel API/database/workers were unchanged.

### Batch 2 ClickHouse database reconciliation — 10 October 2026

Found the bootstrap selecting no database while repository SQL uses unqualified
object names. Legacy objects therefore reside in `default`, whereas service
clients/analytics profiles select `kokonut_analytics`. Corrected `scripts/seed.sh`
to validate a simple `CH_DB` identifier and explicitly select it for readiness
and schema application; no historical SQL files edited. Shell syntax passed.
In the isolated retained clone, the configured database was empty. Applied all
six repository schema files twice successfully, creating 34 objects; default
name/engine/row inventory unchanged. This is a rehearsal, not deployment promotion.

[Bootstrap evidence](builds/2026-10-10-recovery/clickhouse-target-bootstrap.json).
A synthetic sensor projection inserted values 10,20 and then 30 in separate blocks.
Raw and summary counts equal 3, but sum of per-block summary averages is 45 versus
raw average 20. `mv_daily_sensor_summary` uses SummingMergeTree with ordinary
average/min/max/uniq outputs; those statistics cannot safely be summed across
blocks. This is a failed analytics parity gate, not an accepted projection.
[Projection evidence](builds/2026-10-10-recovery/clickhouse-sensor-projection.json).

Batch 4 must introduce versioned corrected rollups using aggregate states or
sum/count plus proper min/max/distinct aggregates, audit all analogous views,
rebuild from retained raw data with explicit backfill, update consumers, and
exercise multi-block/merged output against PostgreSQL queries. Preserve old
views/data until parity passes; never silently replace their definitions.
Legacy physical application tables had zero rows, so no populated historical
transfer was inferred. New synthetic rows exist only in the recovery clone;
clone stopped afterward. Original legacy storage and running deployments unchanged.
Batch 2 remains active for external ownership and remaining recovery gates.
