# Versioned sensor rollup correction

## Interfaces

Schema `schemas/clickhouse/007_sensor_rollups_v2.sql` adds stateful aggregate
materialized views and finalized read views:

- `v_daily_sensor_summary_v2`: day, location_id, sensor_type, avg_value,
  min_value, max_value, total_readings, active_sensors, suspect_readings.
- `v_sensor_reading_rate_v2`: hour, sensor_type, total_readings,
  active_sensors, active_locations.

Read the `v_` interfaces. Their materialized backing views contain aggregate states,
not scalar values. AggregatingMergeTree plus Merge functions handles separate insert
blocks correctly; exact distinct states avoid double-counting repeated sensors.
This changes distinct-count precision from approximate `uniq` to `uniqExact`, with
potential memory cost requiring scale measurement.

## Migration and rollback

1. Preserve raw data, schema metadata and old dashboards; record source image.
2. Stop all analytics writes/outbox delivery and confirm quiescence. Bootstrap
   schema 007 in the configured database. Do not use POPULATE alongside writes.
3. If either new target already contains states, stop and investigate. Never blindly
   backfill again: repeated insertion duplicates counts. Fresh installations need
   no backfill; this step is for existing raw data only.
4. Under continuing quiescence, run the two INSERT SELECT statements in
   `scripts/fixtures/kernel-recovery-sensor-backfill.sql` only after adapting the
   isolated rehearsal to a reviewed deployment operation. ClickHouse does not make
   those two inserts atomic. If one fails, retain the failed state and rebuild both
   new targets from raw under quiescence before retry; do not rerun into partial data.
5. Compare all grouped outputs to raw aggregates and PostgreSQL analytics outputs,
   including unequal blocks, missing groups, suspect readings and repeated sensors.
6. Resume delivery; switch reviewed dashboards to finalized v2 interfaces only
   after parity. Search found no direct repository service/config consumer of the
   replaced daily/rate view names; saved external Metabase queries remain unassessed.

Rollback: revert consumer selection and retain raw data/new states for investigation.
Legacy views are untouched but their known incorrect statistics cannot be treated
as accepted analytics. Prefer direct raw queries until corrected views are accepted.
Do not drop old tables or mutate historical schema files.

## Evidence and open gates

[Isolated results](builds/2026-10-10-recovery/clickhouse-sensor-v2.json): schema
applied twice; empty-target quiesced backfill; subsequent separate insert blocks;
forced FINAL merges. All finalized daily/rate fields match direct raw aggregates.
Three backfilled rows plus two new rows cover two sensors, two locations and one
suspect reading. Clone stopped afterward; no running deployment promoted.

This closes the demonstrated sensor average/count/distinct implementation defect
for synthetic isolated inputs. PostgreSQL/outbox replay parity, external dashboard
queries, large-data resource cost and production backfill remain open. Audit other
SummingMergeTree rollups for non-additive averages, extremes and distinct counts;
this sensor slice does not fix remote-sensing or Web3 rollups. Batch 2 remains active;
this is preparatory Batch 4/Phase 4 correction, not full analytics acceptance.

**Recovery update:** sensor v2 failed crash-replay parity. Prefer `v_daily_sensor_summary_v3` and `v_sensor_reading_rate_v3` over raw rows; see [live recovery](live-outbox-recovery.md).
