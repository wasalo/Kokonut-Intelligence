-- Bounded block deduplication for stable outbox insertion tokens.
-- This is not permanent event uniqueness: replay outside the window needs reconciliation.
ALTER TABLE events_raw MODIFY SETTING non_replicated_deduplication_window = 10000;
ALTER TABLE wallet_events MODIFY SETTING non_replicated_deduplication_window = 10000;
ALTER TABLE sensor_readings MODIFY SETTING non_replicated_deduplication_window = 10000;
ALTER TABLE weather_events MODIFY SETTING non_replicated_deduplication_window = 10000;
ALTER TABLE financial_events MODIFY SETTING non_replicated_deduplication_window = 10000;
ALTER TABLE dlego_events MODIFY SETTING non_replicated_deduplication_window = 10000;
ALTER TABLE remote_sensing_events MODIFY SETTING non_replicated_deduplication_window = 10000;
ALTER TABLE attestation_events MODIFY SETTING non_replicated_deduplication_window = 10000;
