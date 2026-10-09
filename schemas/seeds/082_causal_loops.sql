-- ============================================================
-- 082_causal_loops.sql — Predefined causal loops for farm systems
-- ============================================================

INSERT INTO causal_loop (loop_name, loop_type, domain, description, is_enabled) VALUES
('soil_carbon_reinforcing', 'reinforcing', 'ecological', 'More soil carbon → better water retention → healthier plants → more residue → more soil carbon', TRUE),
('tillage_dependence_trap', 'balancing', 'ecological', 'Tillage breaks compaction short-term but degrades soil structure long-term', TRUE),
('fertilizer_dependency', 'balancing', 'ecological', 'Chemical fertilizer masks declining soil fertility, reducing organic matter investment', TRUE),
('water_table_depletion', 'reinforcing', 'ecological', 'Multiple farms drawing from shared aquifer depletes water table', TRUE),
('knowledge_compounding', 'reinforcing', 'social', 'Training → better practices → better outcomes → more training investment', TRUE),
('certification_value', 'reinforcing', 'financial', 'Certification → premium prices → reinvestment → maintaining certification', TRUE),
('market_price_volatility', 'reinforcing', 'financial', 'High prices → more planting → oversupply → price crash → less planting', TRUE),
('biodiversity_resilience', 'reinforcing', 'ecological', 'More biodiversity → more pest predators → less pesticide → more biodiversity', TRUE),
('community_trust_loop', 'reinforcing', 'social', 'Transparency → trust → participation → better governance → more transparency', TRUE),
('carbon_credit_virtuous', 'reinforcing', 'financial', 'Carbon sequestration → credits → revenue → investment → more sequestration', TRUE)
ON CONFLICT (loop_name) DO NOTHING;

-- Links for soil_carbon_reinforcing
INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'organic_matter', 'soil_carbon', '+', 8760, 'Organic matter decomposes into soil carbon'
FROM causal_loop cl WHERE cl.loop_name = 'soil_carbon_reinforcing';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'soil_carbon', 'water_retention', '+', 720, 'Soil carbon improves water holding capacity'
FROM causal_loop cl WHERE cl.loop_name = 'soil_carbon_reinforcing';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'water_retention', 'plant_health', '+', 168, 'Better water retention supports healthier plants'
FROM causal_loop cl WHERE cl.loop_name = 'soil_carbon_reinforcing';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'plant_health', 'residue_return', '+', 2160, 'Healthier plants produce more residue'
FROM causal_loop cl WHERE cl.loop_name = 'soil_carbon_reinforcing';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'residue_return', 'organic_matter', '+', 4320, 'Residue decomposes into organic matter'
FROM causal_loop cl WHERE cl.loop_name = 'soil_carbon_reinforcing';

-- Links for tillage_dependence_trap
INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'soil_compaction', 'tillage_frequency', '+', 0, 'Compaction drives tillage decisions'
FROM causal_loop cl WHERE cl.loop_name = 'tillage_dependence_trap';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'tillage_frequency', 'soil_structure', '-', 4320, 'Tillage degrades soil structure'
FROM causal_loop cl WHERE cl.loop_name = 'tillage_dependence_trap';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'soil_structure', 'soil_compaction', '-', 8760, 'Poor soil structure leads to more compaction'
FROM causal_loop cl WHERE cl.loop_name = 'tillage_dependence_trap';

-- Links for knowledge_compounding
INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'training_events', 'practice_quality', '+', 2160, 'Training improves practice quality'
FROM causal_loop cl WHERE cl.loop_name = 'knowledge_compounding';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'practice_quality', 'farm_outcomes', '+', 4320, 'Better practices improve outcomes'
FROM causal_loop cl WHERE cl.loop_name = 'knowledge_compounding';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'farm_outcomes', 'training_investment', '+', 0, 'Better outcomes enable more training investment'
FROM causal_loop cl WHERE cl.loop_name = 'knowledge_compounding';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'training_investment', 'training_events', '+', 0, 'Investment funds more training'
FROM causal_loop cl WHERE cl.loop_name = 'knowledge_compounding';

-- Links for certification_value
INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'certification_status', 'price_premium', '+', 0, 'Certification enables premium pricing'
FROM causal_loop cl WHERE cl.loop_name = 'certification_value';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'price_premium', 'revenue', '+', 0, 'Premiums increase revenue'
FROM causal_loop cl WHERE cl.loop_name = 'certification_value';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'revenue', 'certification_investment', '+', 0, 'Revenue funds certification maintenance'
FROM causal_loop cl WHERE cl.loop_name = 'certification_value';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'certification_investment', 'certification_status', '+', 8760, 'Investment maintains certification'
FROM causal_loop cl WHERE cl.loop_name = 'certification_value';

-- Links for biodiversity_resilience
INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'biodiversity', 'pest_predators', '+', 4320, 'Biodiversity supports pest predator populations'
FROM causal_loop cl WHERE cl.loop_name = 'biodiversity_resilience';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'pest_predators', 'pesticide_need', '-', 2160, 'Natural predators reduce pesticide need'
FROM causal_loop cl WHERE cl.loop_name = 'biodiversity_resilience';

INSERT INTO causal_link (loop_id, source_variable, target_variable, polarity, delay_hours, description)
SELECT cl.id, 'pesticide_need', 'biodiversity', '-', 8760, 'Pesticides reduce biodiversity'
FROM causal_loop cl WHERE cl.loop_name = 'biodiversity_resilience';
