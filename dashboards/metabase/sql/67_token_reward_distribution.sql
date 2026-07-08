-- Dashboard SQL: 67_token_reward_distribution
-- Token reward distribution by type, epoch, and metric correlation

SELECT
    trd.location_id,
    l.name AS location_name,
    trd.reward_type,
    trd.token_type,
    trd.distribution_date,
    trd.epoch,
    trd.recipient_name,
    trd.token_amount,
    trd.usd_value,
    trd.linked_metric_key,
    trd.linked_metric_value,
    trd.is_onchain,
    trd.distribution_method,
    trd.notes,
    trd.status
FROM token_reward_distribution trd
JOIN location l ON l.id = trd.location_id
WHERE trd.status IN ('verified', 'published')
  AND l.status = 'active'
ORDER BY trd.distribution_date DESC, trd.reward_type;
