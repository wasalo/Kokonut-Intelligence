-- Adaptive stewardship dashboard: review cadence, triggers, corrective actions, and continuity.
SELECT
  l.name AS location,
  a.review_date,
  a.review_period_start,
  a.review_period_end,
  a.stewardship_scope,
  a.review_cadence,
  a.trigger_thresholds,
  a.observed_triggers,
  a.corrective_actions,
  a.action_completion_pct,
  a.responsible_role,
  a.funding_continuity_plan,
  a.next_review_date,
  a.evidence_maturity,
  a.evidence_maturity_label,
  a.public_summary
FROM v_public_adaptive_stewardship_summary a
JOIN location l ON l.id = a.location_id
ORDER BY a.review_date DESC, a.stewardship_scope;
