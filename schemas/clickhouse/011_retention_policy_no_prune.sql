-- Retention durations and legal holds are owner-configured policy, not schema
-- defaults. This manifest is conditionally applied by
-- scripts/apply-clickhouse-retention.py, which checks each table's metadata and
-- runs REMOVE TTL only when a table-level TTL exists. Do not pipe this file
-- directly into clickhouse-client: ClickHouse rejects REMOVE TTL on a table
-- that has no TTL, so the conditional runner is required for fresh installs
-- and safe reapplication. Removing a TTL does not itself delete rows.
ALTER TABLE events_raw REMOVE TTL;
ALTER TABLE wallet_events REMOVE TTL;
ALTER TABLE sensor_readings REMOVE TTL;
ALTER TABLE weather_events REMOVE TTL;
ALTER TABLE financial_events REMOVE TTL;
ALTER TABLE dlego_events REMOVE TTL;
ALTER TABLE remote_sensing_events REMOVE TTL;
ALTER TABLE attestation_events REMOVE TTL;
