-- Pilot funding + actor participation data for the "State of Kokonut" report.
-- Spans 2021-2024 across the five ecosystem actors (network, dao, foundation,
-- genesis, seeds). References canonical locations/proposals by stable key so the
-- seed is robust regardless of generated UUIDs. Idempotent per AGENTS.md rules.

INSERT INTO funding_round (
    round_code, actor_type, actor_name, round_name, raised_amount, currency,
    source_type, source_detail, period_start, period_end, location_id, status, metadata
) VALUES
    ('FR-2021-NET-01', 'network', 'Kokonut Network', 'Genesis treasury seed', 250000.000000, 'USD',
     'grants', 'Foundational grant to bootstrap the Kokonut Network pilot program.',
     '2021-01-01', '2021-12-31', (SELECT id FROM location WHERE slug = 'adelphi'), 'closed',
     '{"pilot": true}'::jsonb),
    ('FR-2022-DAO-01', 'dao', 'Kokonut DAO', 'DAO community treasury round', 120000.000000, 'USD',
     'token_sale', 'Community treasury top-up via treasury diversification.',
     '2022-02-01', '2022-09-30', NULL, 'closed', '{}'::jsonb),
    ('FR-2022-FDN-01', 'foundation', 'Kokonut Foundation', 'Regenerative research grant', 90000.000000, 'USD',
     'grants', 'External philanthropy grant for syntropic research.',
     '2022-04-01', '2022-12-31', (SELECT id FROM location WHERE slug = 'adelphi'), 'closed',
     '{}'::jsonb),
    ('FR-2023-GEN-01', 'genesis', 'Kokonut Genesis', 'Genesis farm launch capital', 75000.000000, 'USD',
     'equity', 'Founder-aligned launch capital for the first Genesis farm.',
     '2023-01-01', '2023-08-31', (SELECT id FROM location WHERE slug = 'adelphi'), 'closed',
     '{}'::jsonb),
    ('FR-2023-SEE-01', 'seeds', 'Kokonut Seeds', 'Community seed fund', 40000.000000, 'USD',
     'donation', 'Community donation pool redistributed as micro-grants.',
     '2023-03-01', '2023-12-31', NULL, 'closed', '{}'::jsonb),
    ('FR-2024-DAO-02', 'dao', 'Kokonut DAO', 'Adelphi irrigation infrastructure round', 60000.000000, 'USD',
     'revenue', 'Treasury deployment from prior rounds into farm infrastructure.',
     '2024-01-01', '2024-12-31', (SELECT id FROM location WHERE slug = 'adelphi'), 'closed',
     '{}'::jsonb),
    ('FR-2024-NET-02', 'network', 'Kokonut Network', 'Open-source capitalist scaling round', 180000.000000, 'USD',
     'grants', 'Ecosystem scaling grant for open-source tooling.',
     '2024-02-01', '2024-11-30', NULL, 'closed', '{}'::jsonb)
ON CONFLICT (round_code) DO UPDATE SET
    actor_type = EXCLUDED.actor_type,
    actor_name = EXCLUDED.actor_name,
    round_name = EXCLUDED.round_name,
    raised_amount = EXCLUDED.raised_amount,
    currency = EXCLUDED.currency,
    source_type = EXCLUDED.source_type,
    source_detail = EXCLUDED.source_detail,
    period_start = EXCLUDED.period_start,
    period_end = EXCLUDED.period_end,
    location_id = EXCLUDED.location_id,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Actor participation: which entity decided to fund/participate in a project.
INSERT INTO project_funding (
    funding_round_id, location_id, dao_proposal_id, actor_type, amount, token,
    decision_status, decided_at, notes, metadata
) VALUES
    ((SELECT id FROM funding_round WHERE round_code = 'FR-2021-NET-01'),
     (SELECT id FROM location WHERE slug = 'adelphi'), NULL,
     'network', 250000.000000, 'USD', 'executed', '2021-12-15',
     'Initial network treasury seed for the Adelphi pilot.', '{}'::jsonb),
    ((SELECT id FROM funding_round WHERE round_code = 'FR-2022-DAO-01'),
     NULL, NULL,
     'dao', 120000.000000, 'USD', 'executed', '2022-09-30',
     'Community treasury round; capital held for ecosystem deployment.', '{}'::jsonb),
    ((SELECT id FROM funding_round WHERE round_code = 'FR-2022-FDN-01'),
     (SELECT id FROM location WHERE slug = 'adelphi'), NULL,
     'foundation', 90000.000000, 'USD', 'executed', '2022-12-10',
     'Regenerative research grant deployed to Adelphi syntropic trials.', '{}'::jsonb),
    ((SELECT id FROM funding_round WHERE round_code = 'FR-2023-GEN-01'),
     (SELECT id FROM location WHERE slug = 'adelphi'), NULL,
     'genesis', 75000.000000, 'USD', 'executed', '2023-08-20',
     'Genesis farm launch capital.', '{}'::jsonb),
    ((SELECT id FROM funding_round WHERE round_code = 'FR-2023-SEE-01'),
     NULL, NULL,
     'seeds', 40000.000000, 'USD', 'executed', '2023-12-20',
     'Community seed fund micro-grants.', '{}'::jsonb),
    ((SELECT id FROM funding_round WHERE round_code = 'FR-2024-DAO-02'),
     (SELECT id FROM location WHERE slug = 'adelphi'),
     (SELECT id FROM dao_proposal WHERE proposal_code = 'KOK-AD-001'),
     'dao', 500.000000, 'USDC', 'executed', '2024-06-01',
     'DAO-funded Adelphi syntropic bed buildout (proposal KOK-AD-001).', '{}'::jsonb),
    ((SELECT id FROM funding_round WHERE round_code = 'FR-2024-NET-02'),
     NULL, NULL,
     'network', 180000.000000, 'USD', 'executed', '2024-11-30',
     'Open-source scaling round for ecosystem tooling.', '{}'::jsonb)
ON CONFLICT DO NOTHING;
