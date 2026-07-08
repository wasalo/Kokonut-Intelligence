-- ============================================================
-- 061_impact_value_chain.sql — Seeds: departments, roles, tasks, plans, phases, steps
-- ============================================================

-- ============================================================================
-- DEPARTMENTS
-- ============================================================================

INSERT INTO department (id, name, description, status, source_system, source_id, source_raw) VALUES
('a0000000-0000-0000-0000-000000000610', 'Operations', 'Field work, harvesting, maintenance, and daily farm operations', 'active', 'pilot_seed', 'dept-operations', '{"record_type":"department","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000611', 'Ecology', 'Soil health, biodiversity monitoring, carbon tracking, and environmental MRV', 'active', 'pilot_seed', 'dept-ecology', '{"record_type":"department","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000612', 'Finance', 'Accounting, budgeting, financial reporting, and cost allocation', 'active', 'pilot_seed', 'dept-finance', '{"record_type":"department","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000613', 'Community', 'Training, stakeholder engagement, and community programs', 'active', 'pilot_seed', 'dept-community', '{"record_type":"department","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000614', 'Governance', 'DAO governance, council coordination, and compliance', 'active', 'pilot_seed', 'dept-governance', '{"record_type":"department","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    updated_at = NOW();

-- ============================================================================
-- JOB ROLES
-- ============================================================================

INSERT INTO job_role (id, name, description, department_id, status, source_system, source_id, source_raw) VALUES
('a0000000-0000-0000-0000-000000000620', 'Farm Lead', 'Overall farm operations management and strategic direction', 'a0000000-0000-0000-0000-000000000610', 'active', 'pilot_seed', 'role-farm-lead', '{"record_type":"job_role","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000621', 'Community Operations Lead', 'Community engagement, training coordination, and stakeholder relations', 'a0000000-0000-0000-0000-000000000613', 'active', 'pilot_seed', 'role-community-ops', '{"record_type":"job_role","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000622', 'Nursery Steward', 'Seedling production, nursery management, and plant care', 'a0000000-0000-0000-0000-000000000610', 'active', 'pilot_seed', 'role-nursery-steward', '{"record_type":"job_role","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000623', 'MRV Field Coordinator', 'Measurement, reporting, and verification field data collection', 'a0000000-0000-0000-0000-000000000611', 'active', 'pilot_seed', 'role-mrv-coordinator', '{"record_type":"job_role","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000624', 'Finance Manager', 'Financial operations, reporting, and cost management', 'a0000000-0000-0000-0000-000000000612', 'active', 'pilot_seed', 'role-finance-manager', '{"record_type":"job_role","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000625', 'Training Coordinator', 'Training program design, delivery, and impact tracking', 'a0000000-0000-0000-0000-000000000613', 'active', 'pilot_seed', 'role-training-coordinator', '{"record_type":"job_role","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000626', 'DAO Governance Lead', 'DAO proposal management, council coordination, and governance compliance', 'a0000000-0000-0000-0000-000000000614', 'active', 'pilot_seed', 'role-dao-governance', '{"record_type":"job_role","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    department_id = EXCLUDED.department_id,
    updated_at = NOW();

-- ============================================================================
-- LINK EXISTING STAFF TO JOB ROLES AND DEPARTMENTS
-- ============================================================================

UPDATE staff SET
    job_role_id = 'a0000000-0000-0000-0000-000000000620',
    department_id = 'a0000000-0000-0000-0000-000000000610',
    hire_date = '2025-01-15',
    employment_status = 'active'
WHERE id = 'a0000000-0000-0000-0000-000000000060';

UPDATE staff SET
    job_role_id = 'a0000000-0000-0000-0000-000000000621',
    department_id = 'a0000000-0000-0000-0000-000000000613',
    hire_date = '2025-02-01',
    employment_status = 'active'
WHERE id = 'a0000000-0000-0000-0000-000000000061';

UPDATE staff SET
    job_role_id = 'a0000000-0000-0000-0000-000000000622',
    department_id = 'a0000000-0000-0000-0000-000000000610',
    hire_date = '2025-03-15',
    employment_status = 'active'
WHERE id = 'a0000000-0000-0000-0000-000000000062';

UPDATE staff SET
    job_role_id = 'a0000000-0000-0000-0000-000000000623',
    department_id = 'a0000000-0000-0000-0000-000000000611',
    hire_date = '2025-04-01',
    employment_status = 'active'
WHERE id = 'a0000000-0000-0000-0000-000000000063';

-- ============================================================================
-- FARM TASKS (Adelphi)
-- ============================================================================

INSERT INTO farm_task (
    id, location_id, farm_id, plot_id, crop_cycle_id, assignee_id,
    task_name, description, category,
    start_date, end_date, duration_days, priority, status,
    estimated_cost_usd, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000630',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000020', NULL, 'a0000000-0000-0000-0000-000000000062',
 'Prepare nursery beds for Q3 planting', 'Clear and amend nursery beds, prepare compost mix, set up irrigation lines', 'planting',
 '2026-07-01', '2026-07-07', 7, 'high', 'completed',
 150.00, 'pilot_seed', 'adelphi-task-nursery-prep', '{"record_type":"farm_task","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000631',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000021', NULL, 'a0000000-0000-0000-0000-000000000063',
 'Conduct monthly biodiversity survey', 'Survey species in agroforestry corridor using transect method', 'monitoring',
 '2026-07-15', '2026-07-15', 1, 'medium', 'pending',
 50.00, 'pilot_seed', 'adelphi-task-biodiversity', '{"record_type":"farm_task","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000632',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000020', NULL, 'a0000000-0000-0000-0000-000000000060',
 'Apply compost to production beds', 'Spread finished compost from biofactory across syntropic beds', 'maintenance',
 '2026-07-10', '2026-07-12', 3, 'high', 'in_progress',
 200.00, 'pilot_seed', 'adelphi-task-compost', '{"record_type":"farm_task","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000633',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000021', NULL, 'a0000000-0000-0000-0000-000000000061',
 'Host community training workshop', 'Conduct soil management training for 10 community members', 'training',
 '2026-07-20', '2026-07-20', 1, 'high', 'pending',
 100.00, 'pilot_seed', 'adelphi-task-training', '{"record_type":"farm_task","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000634',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010', NULL, NULL, 'a0000000-0000-0000-0000-000000000060',
 'Prepare Q3 financial report', 'Compile expense and revenue data for quarterly DAO report', 'reporting',
 '2026-07-25', '2026-07-31', 7, 'medium', 'pending',
 0.00, 'pilot_seed', 'adelphi-task-financial-report', '{"record_type":"farm_task","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- WEEKLY PLANS (Adelphi)
-- ============================================================================

INSERT INTO weekly_plan (
    id, location_id, farm_id, plan_name, description,
    week_start, week_end, budget_forecast_usd, budget_actual_usd, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000640',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010',
 'Week 27 — Nursery Prep & Compost', 'Prepare nursery beds for Q3 planting and apply compost to production zones',
 '2026-06-29', '2026-07-05', 350.00, 320.00, 'completed',
 'pilot_seed', 'adelphi-weekly-27', '{"record_type":"weekly_plan","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000641',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010',
 'Week 28 — Planting & Training', 'Begin Q3 planting and host community training workshop',
 '2026-07-06', '2026-07-12', 450.00, NULL, 'active',
 'pilot_seed', 'adelphi-weekly-28', '{"record_type":"weekly_plan","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- DEVELOPMENT PHASES (Adelphi)
-- ============================================================================

INSERT INTO development_phase (
    id, location_id, farm_id, phase_name, description,
    phase_order, start_date, end_date, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000650',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010',
 'Land Preparation', 'Clear land, establish boundaries, set up irrigation infrastructure, build biofactory',
 1, '2025-01-01', '2025-06-30', 'completed',
 'pilot_seed', 'adelphi-phase-land-prep', '{"record_type":"development_phase","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000651',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010',
 'Establishment', 'Plant initial crops, establish agroforestry corridor, begin biodiversity monitoring',
 2, '2025-07-01', '2026-06-30', 'active',
 'pilot_seed', 'adelphi-phase-establishment', '{"record_type":"development_phase","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000652',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010',
 'Production', 'Full-scale harvest, sales, and carbon credit generation',
 3, '2026-07-01', '2028-06-30', 'pending',
 'pilot_seed', 'adelphi-phase-production', '{"record_type":"development_phase","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- FRAMEWORK STEPS (Adelphi — Kokonut Framework)
-- ============================================================================

INSERT INTO framework_step (
    id, location_id, farm_id, step_name, description,
    step_order, step_type, duration_days, prerequisites, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000660',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010',
 'Baseline Assessment', 'Establish soil, water, and biodiversity baselines; document current state',
 1, 'preparation', 30, '[]'::jsonb, 'completed',
 'pilot_seed', 'adelphi-step-baseline', '{"record_type":"framework_step","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000661',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010',
 'Soil Preparation', 'Apply compost, biochar, and organic amendments; establish living cover',
 2, 'implementation', 60, '["a0000000-0000-0000-0000-000000000660"]'::jsonb, 'completed',
 'pilot_seed', 'adelphi-step-soil-prep', '{"record_type":"framework_step","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000662',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010',
 'Planting & Establishment', 'Plant crops, establish agroforestry corridor, install irrigation',
 3, 'implementation', 90, '["a0000000-0000-0000-0000-000000000661"]'::jsonb, 'completed',
 'pilot_seed', 'adelphi-step-planting', '{"record_type":"framework_step","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000663',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010',
 'Monitoring & Data Collection', 'Regular soil, biodiversity, and remote sensing monitoring',
 4, 'monitoring', 365, '["a0000000-0000-0000-0000-000000000662"]'::jsonb, 'in_progress',
 'pilot_seed', 'adelphi-step-monitoring', '{"record_type":"framework_step","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000664',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010',
 'Verification & Attestation', 'Submit data for verification, obtain on-chain attestations',
 5, 'verification', 30, '["a0000000-0000-0000-0000-000000000663"]'::jsonb, 'pending',
 'pilot_seed', 'adelphi-step-verification', '{"record_type":"framework_step","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000665',
 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010',
 'Publication & Reporting', 'Publish impact reports, share findings with network',
 6, 'publication', 14, '["a0000000-0000-0000-0000-000000000664"]'::jsonb, 'pending',
 'pilot_seed', 'adelphi-step-publication', '{"record_type":"framework_step","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();
