-- Pilot strategic reserves for the Strategic Reserve layer.
-- Sourced from existing primitives where possible:
--   * commons_reserve  -> commons_redistribution_policy.reserve_allocation_pct (Adelphi)
--   * financial_ringfence -> funding_round raised totals (network/dao held capital)
--   * carbon_buffer / seed_vault / capability_standby -> fixed pilot targets
-- Idempotent per AGENTS.md (ON CONFLICT DO UPDATE for canonical rows).

INSERT INTO strategic_reserve (
    reserve_code, reserve_type, entity_scope, scope_id, name, description,
    held_quantity, capacity_target, unit, refill_policy,
    trigger_metric_key, trigger_operator, trigger_threshold,
    preempt_threshold_pct, status, metadata
) VALUES
    ('SR-ADL-COMMONS-01', 'commons_reserve', 'farm',
     (SELECT id FROM location WHERE slug = 'kokonut-adelphi'),
     'Adelphi Commons Reserve',
     'Ring-fenced share of farm net revenue held for community/commons deployment, sourced from the Adelphi commons redistribution policy reserve allocation.',
      COALESCE((SELECT COALESCE(reserve_allocation_pct, 0) * 1000 FROM commons_redistribution_policy
         WHERE location_id = (SELECT id FROM location WHERE slug = 'kokonut-adelphi') LIMIT 1), 0),
      15000.000000, 'usd', 'percentage',
     'farm_net_revenue', 'gte', 0, 'active',
     '{"sourced_from": "commons_redistribution_policy.reserve_allocation_pct", "pilot": true}'::jsonb),

    ('SR-NET-FIN-01', 'financial_ringfence', 'network', NULL,
     'Kokonut Network Ring-Fenced Reserve',
     'Network treasury capital held outside ordinary operations, sourced from closed network/DAO funding rounds (pilot seed totals).',
      COALESCE((SELECT COALESCE(SUM(raised_amount), 0) FROM funding_round
         WHERE actor_type IN ('network', 'dao') AND status = 'closed'), 0),
      600000.000000, 'usd', 'event_driven',
     'network_treasury_drawdown', 'gt', 0, 'active',
     '{"sourced_from": "funding_round", "pilot": true}'::jsonb),

    ('SR-ADL-CARBON-01', 'carbon_buffer', 'farm',
     (SELECT id FROM location WHERE slug = 'kokonut-adelphi'),
     'Adelphi Carbon Permanence Buffer',
     'Carbon credit buffer pool held against reversal/permanence risk (mirrors credit_class buffer_pool_pct).',
      20000.000000, 100000.000000, 'tonnes_co2e', 'fixed',
      'carbon_reversal_risk', 'gt', 5, 0.8, 'active',
      '{"mirrors": "credit_class.buffer_pool_account", "pilot_target": true}'::jsonb),

    ('SR-ADL-SEED-01', 'seed_vault', 'farm',
     (SELECT id FROM location WHERE slug = 'kokonut-adelphi'),
     'Adelphi Agro-biodiversity Seed Vault',
     'Distinct crop lines and tree species held in reserve as regenerative insurance (Svalbard/Frozen Ark analog).',
      COALESCE((SELECT COALESCE(COUNT(DISTINCT species_name), 0) FROM tree_inventory
         WHERE location_id = (SELECT id FROM location WHERE slug = 'kokonut-adelphi'))
      + (SELECT COALESCE(COUNT(DISTINCT crop_id), 0) FROM crop_cycle
         WHERE location_id = (SELECT id FROM location WHERE slug = 'kokonut-adelphi')), 0),
      50.000000, 'distinct_lines', 'fixed',
     'distinct_species_count', 'lt', 30, 'active',
     '{"sourced_from": "tree_inventory + crop_cycle", "pilot_target": true}'::jsonb),

    ('SR-NET-CAP-01', 'capability_standby', 'network', NULL,
     'Kokonut Standby Capability Reserve',
     'Standby analytics/infrastructure capacity held outside market use, activated only on monitored shortage (TSO strategic-reserve analog).',
      1.000000, 3.000000, 'capacity_units', 'event_driven',
      'service_availability_pct', 'lt', 99, 0.8, 'active',
      '{"analog": "TSO strategic reserve", "pilot_target": true}'::jsonb)
ON CONFLICT (reserve_code) DO UPDATE SET
    reserve_type = EXCLUDED.reserve_type,
    entity_scope = EXCLUDED.entity_scope,
    scope_id = EXCLUDED.scope_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    held_quantity = EXCLUDED.held_quantity,
    capacity_target = EXCLUDED.capacity_target,
    unit = EXCLUDED.unit,
    refill_policy = EXCLUDED.refill_policy,
    trigger_metric_key = EXCLUDED.trigger_metric_key,
    trigger_operator = EXCLUDED.trigger_operator,
    trigger_threshold = EXCLUDED.trigger_threshold,
    preempt_threshold_pct = EXCLUDED.preempt_threshold_pct,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
