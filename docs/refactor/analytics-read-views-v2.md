# Remaining analytics rollup corrections

Schema `008_analytics_read_views_v2.sql` adds four ordinary read views over raw
ClickHouse tables. Existing materialized views remain unchanged.

| Read interface | Correction |
| --- | --- |
| v_monthly_wallet_unique_active_v2 | Repeated wallets counted once across insert blocks |
| v_daily_dlego_protocol_usage_v2 | Preserves day/protocol/action/chain dimensions |
| v_dlego_value_by_location_v2 | Preserves month/location/protocol dimensions |
| v_daily_remote_sensing_summary_v2 | Nullable averages and min/max computed over raw observations |

These require no backfill and avoid dependence on unsafe legacy merged summaries.
They preserve existing numeric types, including Decimal128 amounts and nullable
remote-sensing observations. Wallet distinct counting remains exact. Sensor v2
stateful interfaces and their explicit backfill are documented separately.

## Rollup audit

All 11 repository materialized-view definitions reviewed in schemas 002,003,006:
additive event/wallet/financial totals have complete sorting dimensions; hourly
sensor and daily weather use aggregate states; the two sensor views were corrected
in 007; monthly distinct wallets, both Digital Lego summaries and remote-sensing
summary need the new 008 interfaces. Existing aggregate-state consumers must call
Merge functions with the intended grouping; additive summaries must sum remaining
unmerged rows. Ordinary portfolio views query raw data and do not share this
SummingMergeTree defect. This structural audit does not prove every query's domain
meaning, decimal conversion accuracy, source attribution or ingestion idempotency.

## Adoption and rollback

Apply schema 008 in the selected analytics database, compare output to raw and
PostgreSQL analytics, inventory saved Metabase queries, then deliberately switch
consumers to v2. Search the actual saved queries before claiming dashboard parity.
No automatic legacy drops or ALTERs. Revert consumer selection to raw queries if
needed; legacy summaries with known defects cannot serve as accepted rollback
results. Raw views scan source tables and need volume/latency/resource measurement;
future materialization must preserve these read contracts and pass the same checks.

[Isolated evidence](builds/2026-10-10-recovery/clickhouse-remaining-v2.json).
Fixtures use repeated wallets, separate insert blocks, action/chain/protocol
variation, nullable NDVI/all-null MSAVI, and cloud extrema. Outputs are compared
before and after raw and legacy materialized-table FINAL merges. No chain calls
or production promotion. Remaining gates: PostgreSQL/outbox parity, dashboard
adoption and scale measurements. Batch 2 remains active; Batch 4 is preparatory.
