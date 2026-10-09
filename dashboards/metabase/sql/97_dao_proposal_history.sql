-- DAO proposal history: governance events from Gnosis Moloch DAO.
SELECT
  ge.event_type,
  ge.proposal_id,
  ge.proposal_title,
  ge.vote_value,
  ge.shares_offered,
  ge.loot_offered,
  ge.total_yes_votes,
  ge.total_no_votes,
  ge.processed,
  ge.block_number,
  ge.event_timestamp,
  wp.address AS voter_address,
  wp.label AS voter_label
FROM governance_event ge
LEFT JOIN wallet_profile wp ON wp.id = ge.wallet_id
WHERE ge.chain = 'gnosis'
ORDER BY ge.event_timestamp DESC;
