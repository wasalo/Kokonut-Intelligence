-- ============================================================
-- 064-068 Impact Network Seeds: Organization, Funding, Landscape, Bounties, Office
-- ============================================================

-- ============================================================================
-- 064: Organization
-- ============================================================================

INSERT INTO organization (
    id, org_key, name, org_type, description, governance_model, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000700',
 'kokonut-adelphi', 'Kokonut Adelphi', 'cooperative',
 'Adelphi syntropic farm in Sabana Grande de Boya, Dominican Republic. Pilot demonstration farm for the Kokonut Network.',
 'moloch_dao', 'active',
 'pilot_seed', 'org-kokonut-adelphi',
 '{"record_type":"organization","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Link existing location to organization
UPDATE location SET organization_id = 'a0000000-0000-0000-0000-000000000700'
WHERE id = 'a0000000-0000-0000-0000-000000000001';

-- Organization member
INSERT INTO organization_member (
    id, organization_id, location_id, farm_id, membership_type, join_date, role, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000710',
 'a0000000-0000-0000-0000-000000000700',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000010',
 'owned', '2025-01-01', 'primary', 'active',
 'pilot_seed', 'org-member-adelphi',
 '{"record_type":"organization_member","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- 065: Funding Flow
-- ============================================================================

-- Donor
INSERT INTO donor (
    id, display_name, donor_type, is_anonymous, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000720',
 'Kokonut DAO Treasury', 'dao', FALSE, 'active',
 'pilot_seed', 'donor-kokonut-dao',
 '{"record_type":"donor","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000721',
 'Anonymous Supporter', 'individual', TRUE, 'active',
 'pilot_seed', 'donor-anonymous-001',
 '{"record_type":"donor","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000722',
 'Ma Earth Foundation', 'institutional', FALSE, 'active',
 'pilot_seed', 'donor-ma-earth',
 '{"record_type":"donor","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();

-- Funding campaign
INSERT INTO funding_campaign (
    id, campaign_key, location_id, organization_id, campaign_name, campaign_type,
    goal_amount, raised_amount, start_date, end_date, description, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000730',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000700',
 'Adelphi Syntropic Expansion', 'crowdfunding',
 45000.00, 20500.00, '2025-01-01', '2025-12-31',
 'Fund the expansion of Adelphi syntropic farm with new planting zones, biofactory capacity, and community training programs.',
 'active',
 'pilot_seed', 'campaign-adelphi-expansion',
 '{"record_type":"funding_campaign","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    raised_amount = EXCLUDED.raised_amount,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Donations
INSERT INTO donation (
    id, campaign_id, donor_id, location_id, amount, currency, payment_method,
    donation_date, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000740',
 'a0000000-0000-0000-0000-000000000730',
 'a0000000-0000-0000-0000-000000000720',
 'a0000000-0000-0000-0000-000000000001',
 13500.00, 'USD', 'crypto',
 '2025-01-15', 'completed',
 'pilot_seed', 'donation-dao-001',
 '{"record_type":"donation","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000741',
 'a0000000-0000-0000-0000-000000000730',
 'a0000000-0000-0000-0000-000000000722',
 'a0000000-0000-0000-0000-000000000001',
 5000.00, 'USD', 'bank_transfer',
 '2025-03-01', 'completed',
 'pilot_seed', 'donation-ma-earth-001',
 '{"record_type":"donation","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000742',
 'a0000000-0000-0000-0000-000000000730',
 'a0000000-0000-0000-0000-000000000721',
 'a0000000-0000-0000-0000-000000000001',
 2000.00, 'USD', 'crypto',
 '2025-06-15', 'completed',
 'pilot_seed', 'donation-anonymous-001',
 '{"record_type":"donation","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();

-- Impact payout rule
INSERT INTO impact_payout_rule (
    id, location_id, campaign_id, metric_id, payout_type, trigger_condition,
    payout_amount, payout_currency, payout_recipient, attestation_required,
    min_evidence_maturity, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000750',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000730',
 (SELECT id FROM metric_definition WHERE metric_key = 'soil_carbon_delta' LIMIT 1),
 'threshold', 'soil_carbon_delta >= 2.0 AND evidence_maturity >= 4',
 5000.00, 'USD', 'farm_operator', TRUE, 4, 'active',
 'pilot_seed', 'payout-rule-soil-carbon',
 '{"record_type":"impact_payout_rule","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- 067: Impact Bounties
-- ============================================================================

INSERT INTO impact_bounty (
    id, bounty_key, location_id, bounty_name, bounty_type,
    description, data_requirement, reward_amount, reward_currency,
    max_submissions, min_evidence_maturity, expiration_date,
    bounty_status, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000760',
 'a0000000-0000-0000-0000-000000000001',
 'Soil Sampling Campaign — Q1 2026', 'soil_sampling',
 'Collect soil samples from all production zone beds. Submit pH, organic matter, and NPK readings with GPS coordinates and photo evidence.',
 'Submit soil sample data with: pH, organic_matter_pct, nitrogen_ppm, phosphorus_ppm, potassium_ppm, GPS coordinates, lab report photo.',
 50.00, 'USD', 10, 2, '2026-03-31',
 'active', 'published',
 'pilot_seed', 'bounty-soil-q1-2026',
 '{"record_type":"impact_bounty","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000761',
 'a0000000-0000-0000-0000-000000000001',
 'Biodiversity Survey — Agroforestry Corridor', 'species_identification',
 'Survey the agroforestry corridor for bird, insect, and plant species. Submit species names, counts, GPS coordinates, and observation method.',
 'Submit species observations with: species_name, count, GPS coordinates, observation_method, habitat_type.',
 100.00, 'USD', 5, 3, '2026-06-30',
 'active', 'published',
 'pilot_seed', 'bounty-biodiversity-corridor',
 '{"record_type":"impact_bounty","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    bounty_status = EXCLUDED.bounty_status,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- 068: Impact Office
-- ============================================================================

-- Impact office run
INSERT INTO impact_office_run (
    id, run_key, run_name, run_type, trigger_source, location_id, organization_id,
    status, started_at, completed_at,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000770',
 'adelphi-q1-2026-full-cycle',
 'Adelphi Q1 2026 Full Impact Cycle',
 'full_cycle', 'manual',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000700',
 'completed', '2026-01-01T08:00:00Z', '2026-01-01T08:15:00Z',
 'pilot_seed', 'office-run-adelphi-q1',
 '{"record_type":"impact_office_run","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    completed_at = EXCLUDED.completed_at;

-- Impact office steps
INSERT INTO impact_office_step (
    id, run_id, step_order, step_type, step_name, step_status, started_at, completed_at,
    source_system, source_id
) VALUES
('a0000000-0000-0000-0000-000000000780',
 'a0000000-0000-0000-0000-000000000770', 1, 'ingest', 'Ingest weather and sensor data',
 'completed', '2026-01-01T08:00:00Z', '2026-01-01T08:02:00Z',
 'pilot_seed', 'office-step-1'),
('a0000000-0000-0000-0000-000000000781',
 'a0000000-0000-0000-0000-000000000770', 2, 'compute_metric', 'Compute governed metrics',
 'completed', '2026-01-01T08:02:00Z', '2026-01-01T08:05:00Z',
 'pilot_seed', 'office-step-2'),
('a0000000-0000-0000-0000-000000000782',
 'a0000000-0000-0000-0000-000000000770', 3, 'generate_agent_task', 'Generate agent summaries',
 'completed', '2026-01-01T08:05:00Z', '2026-01-01T08:08:00Z',
 'pilot_seed', 'office-step-3'),
('a0000000-0000-0000-0000-000000000783',
 'a0000000-0000-0000-0000-000000000770', 4, 'review', 'Review evidence gaps and create bounties',
 'completed', '2026-01-01T08:08:00Z', '2026-01-01T08:10:00Z',
 'pilot_seed', 'office-step-4'),
('a0000000-0000-0000-0000-000000000784',
 'a0000000-0000-0000-0000-000000000770', 5, 'refresh_view', 'Refresh materialized views and dashboards',
 'completed', '2026-01-01T08:10:00Z', '2026-01-01T08:12:00Z',
 'pilot_seed', 'office-step-5'),
('a0000000-0000-0000-0000-000000000785',
 'a0000000-0000-0000-0000-000000000770', 6, 'export_report', 'Generate impact reports',
 'completed', '2026-01-01T08:12:00Z', '2026-01-01T08:15:00Z',
 'pilot_seed', 'office-step-6')
ON CONFLICT (id) DO UPDATE SET
    step_status = EXCLUDED.step_status,
    completed_at = EXCLUDED.completed_at;

-- Impact office alert
INSERT INTO impact_office_alert (
    id, run_id, alert_type, severity, message, resolution_status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000790',
 'a0000000-0000-0000-0000-000000000770',
 'campaign_goal_reached', 'info',
 'Adelphi Syntropic Expansion campaign reached 45% of funding goal ($20,500 of $45,000).',
 'resolved',
 'pilot_seed', 'office-alert-campaign',
 '{"record_type":"impact_office_alert","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    resolution_status = EXCLUDED.resolution_status,
    updated_at = NOW();
