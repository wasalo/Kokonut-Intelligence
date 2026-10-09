-- Reward calibration: token reward distribution and overjustification risk signals.
SELECT
  l.name AS location,
  trd.distribution_method,
  trd.total_rewards_distributed,
  trd.recipient_count,
  trd.avg_reward_per_recipient,
  trd.period_start,
  trd.period_end,
  trd.overjustification_risk_level,
  trd.correlation_with_intrinsic_motivation
FROM token_reward_distribution trd
JOIN location l ON l.id = trd.location_id
WHERE trd.status = 'active'
ORDER BY trd.period_end DESC;
