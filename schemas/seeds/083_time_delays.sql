-- ============================================================
-- 083_time_delays.sql — Predefined action-effect delay mappings
-- ============================================================

INSERT INTO time_delay (action_type, effect_type, expected_delay_hours, min_delay_hours, max_delay_hours, domain, description) VALUES
('cover_crop_planting', 'soil_carbon_increase', 17520, 8760, 43800, 'ecological', 'Cover crops take 2-5 years to significantly increase soil carbon'),
('organic_certification', 'price_premium', 26280, 17520, 35040, 'financial', 'Organic certification typically yields price premium after 3-year transition'),
('training_event', 'practice_adoption', 4320, 2160, 8760, 'social', 'Training effects take 3-12 months to fully manifest'),
('irrigation', 'soil_moisture_increase', 6, 1, 24, 'ecological', 'Soil moisture responds to irrigation within hours'),
('fertilizer_application', 'yield_response', 1008, 336, 1344, 'ecological', 'Crop response to fertilizer takes 2-6 weeks'),
('compost_application', 'soil_structure_improvement', 4320, 2160, 8760, 'ecological', 'Compost improves soil structure over 6-12 months'),
('pest_management_intervention', 'pest_population_decline', 336, 72, 720, 'ecological', 'Pest populations respond to management in 1-30 days'),
('water_conservation', 'aquifer_recovery', 26280, 8760, 87600, 'ecological', 'Groundwater recovery takes years to decades'),
('carbon_credit_issuance', 'revenue_recognition', 720, 168, 2160, 'financial', 'Carbon credit revenue recognized in 1-12 weeks'),
('governance_reform', 'community_trust_increase', 8760, 4320, 17520, 'governance', 'Trust building takes 1-2 years'),
('diversification', 'income_stability', 8760, 4320, 17520, 'financial', 'Diversification effects take 1-2 years to stabilize'),
('soil_amendment', 'ph_adjustment', 2160, 720, 4320, 'ecological', 'Soil pH responds to amendments over 3-12 months'),
('agroforestry_planting', 'microclimate_improvement', 17520, 8760, 43800, 'ecological', 'Tree canopy effects take 2-5 years to mature'),
('community_engagement', 'social_cohesion', 4320, 2160, 8760, 'social', 'Social cohesion builds over 6-12 months'),
('digital_infrastructure', 'data_quality_improvement', 2160, 720, 4320, 'governance', 'Data systems improve over 3-12 months'),
('mulching', 'soil_moisture_retention', 720, 168, 2160, 'ecological', 'Mulch effects on moisture visible in 1-4 weeks'),
('biological_control_introduction', 'pest_suppression', 4320, 2160, 8760, 'ecological', 'Biocontrol agents establish over 6-12 months'),
('drip_irrigation_installation', 'water_use_efficiency', 2160, 720, 4320, 'ecological', 'Efficiency gains realized over 3-12 months'),
('crop_rotation_change', 'disease_pressure_reduction', 8760, 4320, 17520, 'ecological', 'Rotation effects build over 1-2 seasons'),
('hedgerow_planting', 'wind_protection', 17520, 8760, 43800, 'ecological', 'Hedgerows take 2-5 years to provide wind protection')
ON CONFLICT (action_type, effect_type) DO NOTHING;
