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
('default_processing_uplift', '1.3', 'Default uplift for unknown crops'),
-- Scoring formulas — crop_mix
('crop_mix_gap_normalizer', '10', 'NOI gap normalization divisor ($/ha per point)'),
('crop_mix_confidence_threshold', '4', 'Min completed cycles for high confidence'),
-- Scoring formulas — loss_reduction
('loss_rate_score_multiplier', '5', 'Loss rate to score multiplier (20% = 100)'),
('loss_rate_confidence_threshold', '3', 'Min loss events for high confidence'),
-- Scoring formulas — buyer_channel
('buyer_payment_weight', '0.4', 'Payment rate weight in buyer scoring'),
('buyer_returns_weight', '0.3', 'Returns rate weight in buyer scoring'),
('buyer_netsale_weight', '0.3', 'Net-per-sale weight in buyer scoring'),
('buyer_netsale_normalizer', '100', 'Net-per-sale normalization divisor'),
('buyer_count_multiplier', '25', 'Unique buyers to score multiplier'),
('buyer_confidence_threshold', '2', 'Min buyers for medium confidence'),
-- Scoring formulas — value_added
('value_added_uplift_multiplier', '30', 'Uplift-to-score multiplier'),
('value_added_infra_bonus', '1.3', 'Infrastructure bonus multiplier'),
('value_added_cost_assumption', '0.5', 'Processing cost increase assumption (50%)'),
-- Scoring formulas — web3_replication
('web3_funding_sources_multiplier', '20', 'Funding sources to score multiplier'),
('web3_funding_bonus', '20', 'Positive net funding bonus'),
-- Scoring formulas — bioinput
('bioinput_share_multiplier', '1.5', 'Bioinput share to score multiplier'),
('bioinput_biofactory_bonus', '50', 'Biofactory presence bonus'),
('bioinput_default_capacity', '500', 'Default biofactory capacity (liters)'),
('bioinput_switching_fallback', '0.3', 'Switching benefit fallback (30% of conventional)'),
-- Scoring formulas — public_goods
('public_goods_allocation_multiplier', '10', 'Allocation rate to score multiplier'),
('public_goods_target_pct', '0.05', 'Target public goods allocation (5% of revenue)'),
-- Scoring formulas — ecological_verification
('ecological_carbon_weight', '25', 'Carbon data presence score weight'),
('ecological_species_weight', '25', 'Species data presence score weight'),
('ecological_claims_weight', '30', 'Claims data presence score weight'),
('ecological_forecast_weight', '20', 'Forecast presence score weight'),
-- Scoring formulas — partner_sponsorship
('partner_count_multiplier', '15', 'Partners to score multiplier'),
('partner_revenue_bonus', '20', 'Revenue presence bonus'),
-- Scoring formulas — regional_clusters
('regional_nearby_multiplier', '20', 'Nearby locations to score multiplier'),
('regional_farm_multiplier', '10', 'Farms to score multiplier'),
('regional_ha_per_nearby', '10', 'Estimated hectares per nearby location'),
-- Analyzer dimension weights
('weight_crop_mix', '1.5', 'Dimension weight for crop mix optimization'),
('weight_loss_reduction', '1.2', 'Dimension weight for loss-rate reduction'),
('weight_buyer_channel', '1.0', 'Dimension weight for buyer/channel selection'),
('weight_value_added', '1.0', 'Dimension weight for value-added processing'),
('weight_web3_replication', '0.8', 'Dimension weight for Web3-funded replication'),
('weight_bioinput', '0.8', 'Dimension weight for bioinput production'),
('weight_public_goods', '0.7', 'Dimension weight for public-goods funding loops'),
('weight_ecological_verification', '1.0', 'Dimension weight for ecological verification'),
('weight_partner_sponsorship', '0.8', 'Dimension weight for partner sponsorship'),
('weight_regional_clusters', '0.6', 'Dimension weight for regional farm clusters')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    description = EXCLUDED.description,
    updated_at = NOW();
