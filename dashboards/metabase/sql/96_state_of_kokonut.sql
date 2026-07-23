-- State of Kokonut: ecosystem-level overview with funding and project participation.
SELECT
  fr.actor_type,
  fr.actor_name,
  fr.funding_round_name,
  fr.amount_raised,
  fr.currency,
  fr.round_date,
  pf.project_name,
  pf.amount_allocated,
  pf.participation_type
FROM funding_round fr
LEFT JOIN project_funding pf ON pf.funding_round_id = fr.id
WHERE fr.status = 'active'
ORDER BY fr.round_date DESC;
