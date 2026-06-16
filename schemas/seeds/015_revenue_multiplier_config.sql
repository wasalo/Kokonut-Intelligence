-- Revenue multiplier dimension configuration
INSERT INTO revenue_multiplier_config (config_key, config_value, description) VALUES
('processing_uplift', '{"Maize": {"flour": 1.8, "porridge_mix": 2.2, "animal_feed": 1.3}, "Cassava": {"flour": 2.0, "chips": 1.5, "starch": 2.5}, "Beans": {"packaged": 1.4, "flour": 1.6, "sprouted": 2.0}, "Sweet Potato": {"dried_chips": 1.6, "flour": 1.8, "puree": 2.0}}', 'Processing uplift multipliers by crop and type'),
('replication_cost_usd', '15000', 'Cost to replicate one farm ($USD)'),
('loop_multiplier', '2.5', 'Public goods loop multiplier'),
('carbon_credit_price_usd', '25.0', 'Carbon credit price per tonne CO2e'),
('biodiversity_credit_price_usd', '35.0', 'Biodiversity credit price per unit'),
('impact_certificate_price_usd', '10.0', 'Impact certificate price per verified claim'),
('shared_savings_per_ha_usd', '50', 'Shared infrastructure savings per hectare'),
('new_partners_potential', '3', 'Conservative estimate of new partner count'),
('loss_reduction_target_pct', '50', 'Target loss reduction percentage'),
('buyer_uplift_pct', '30', 'Buyer optimization uplift potential'),
('bioinput_savings_pct', '70', 'Bioinput production savings with biofactory'),
('bioinput_switching_benefit_pct', '50', 'Switching benefit from conventional to bioinput'),
('default_processing_uplift', '1.3', 'Default uplift for unknown crops')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    description = EXCLUDED.description,
    updated_at = NOW();
