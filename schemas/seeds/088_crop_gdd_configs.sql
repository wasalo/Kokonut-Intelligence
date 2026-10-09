-- 088_crop_gdd_configs.sql
-- Growing Degree Day configurations for common crops
-- FAO-56 crop coefficients and phenological stage thresholds

BEGIN;

INSERT INTO crop_gdd_config (crop_name, base_temp_c, upper_temp_c, total_gdd_required, stages, kc_values, source)
VALUES
    ('Maize', 10.0, 30.0, 2500,
     '[
        {"name": "emergence", "gdd": 100, "description": "Seedling emergence and early leaf development"},
        {"name": "vegetative", "gdd": 500, "description": "Rapid vegetative growth, leaf area expansion"},
        {"name": "tasseling", "gdd": 1100, "description": "Tassel emergence, pollen shed begins"},
        {"name": "silking", "gdd": 1200, "description": "Silk emergence, pollination, kernel set"},
        {"name": "maturity", "gdd": 2500, "description": "Grain fill complete, black layer formation"}
     ]'::jsonb,
     '{"initial": 0.3, "development": 0.75, "mid": 1.15, "late": 0.6}'::jsonb,
     'FAO-56 Table 12, Stewart & Hagen 1988'),

    ('Beans', 10.0, 30.0, 1400,
     '[
        {"name": "emergence", "gdd": 80, "description": "Seedling emergence"},
        {"name": "vegetative", "gdd": 300, "description": "Leaf and stem growth"},
        {"name": "flowering", "gdd": 500, "description": "Flower initiation and bloom"},
        {"name": "pod_fill", "gdd": 800, "description": "Pod development and seed fill"},
        {"name": "maturity", "gdd": 1400, "description": "Pod dry-down, physiological maturity"}
     ]'::jsonb,
     '{"initial": 0.35, "development": 0.7, "mid": 1.1, "late": 0.65}'::jsonb,
     'FAO-56 Irrigation and Drainage Paper 56'),

    ('Cassava', 15.0, 35.0, 4500,
     '[
        {"name": "emergence", "gdd": 150, "description": "Sprouting and root establishment"},
        {"name": "vegetative", "gdd": 800, "description": "Canopy expansion, stem elongation"},
        {"name": "tuber_init", "gdd": 1500, "description": "Tuber initiation and early bulking"},
        {"name": "bulking", "gdd": 3000, "description": "Active starch accumulation in storage roots"},
        {"name": "maturity", "gdd": 4500, "description": "Maximum starch content, ready for harvest"}
     ]'::jsonb,
     '{"initial": 0.4, "development": 0.7, "mid": 1.1, "late": 0.7}'::jsonb,
     'CIAT/IFPRI cassava growth models'),

    ('Sweet Potato', 10.0, 35.0, 2200,
     '[
        {"name": "emergence", "gdd": 100, "description": "Slip establishment and early root growth"},
        {"name": "vegetative", "gdd": 400, "description": "Vine and canopy expansion"},
        {"name": "tuber_init", "gdd": 800, "description": "Storage root initiation"},
        {"name": "bulking", "gdd": 1500, "description": "Active bulking of storage roots"},
        {"name": "maturity", "gdd": 2200, "description": "Maximum dry matter, harvest ready"}
     ]'::jsonb,
     '{"initial": 0.4, "development": 0.75, "mid": 1.05, "late": 0.6}'::jsonb,
     'CIP sweet potato production guide'),

    ('Coffee', 10.0, 30.0, 3000,
     '[
        {"name": "emergence", "gdd": 120, "description": "Seedling establishment"},
        {"name": "vegetative", "gdd": 600, "description": "Branch and canopy development"},
        {"name": "flowering", "gdd": 1200, "description": "Floral induction and bloom"},
        {"name": "cherry_development", "gdd": 2000, "description": "Cherry development and maturation"},
        {"name": "maturity", "gdd": 3000, "description": "Cherry harvest maturity"}
     ]'::jsonb,
     '{"initial": 0.4, "development": 0.7, "mid": 1.15, "late": 0.7}'::jsonb,
     'ICO/World Coffee Research phenology guide'),

    ('Avocado', 10.0, 30.0, 3500,
     '[
        {"name": "flush", "gdd": 200, "description": "New vegetative flush emergence"},
        {"name": "vegetative", "gdd": 800, "description": "Canopy expansion and wood hardening"},
        {"name": "flowering", "gdd": 1500, "description": "Floral induction and bloom"},
        {"name": "fruit_development", "gdd": 2500, "description": "Fruit set and cell division"},
        {"name": "maturity", "gdd": 3500, "description": "Fruit oil accumulation and harvest"}
     ]'::jsonb,
     '{"initial": 0.4, "development": 0.75, "mid": 1.2, "late": 0.8}'::jsonb,
     'UC Riverside avocado phenology'),

    ('Tomato', 10.0, 30.0, 1800,
     '[
        {"name": "emergence", "gdd": 80, "description": "Seedling emergence and cotyledon expansion"},
        {"name": "vegetative", "gdd": 350, "description": "Stem elongation, leaf development"},
        {"name": "flowering", "gdd": 600, "description": "First flower opening"},
        {"name": "fruit_set", "gdd": 900, "description": "Fruit set and initial growth"},
        {"name": "maturity", "gdd": 1800, "description": "Fruit color change and harvest"}
     ]'::jsonb,
     '{"initial": 0.4, "development": 0.75, "mid": 1.15, "late": 0.8}'::jsonb,
     'FAO-56, UC Davis tomato production'),

    ('Banana', 12.0, 35.0, 3200,
     '[
        {"name": "establishment", "gdd": 200, "description": "Sucker establishment and early growth"},
        {"name": "vegetative", "gdd": 1000, "description": "Pseudostem elongation, leaf production"},
        {"name": "flowering", "gdd": 1800, "description": "Bunch emergence and flowering"},
        {"name": "fruit_fill", "gdd": 2600, "description": "Finger development and filling"},
        {"name": "maturity", "gdd": 3200, "description": "Fruit maturity and harvest"}
     ]'::jsonb,
     '{"initial": 0.4, "development": 0.7, "mid": 1.2, "late": 0.85}'::jsonb,
     'FAO Banana Production Handbook')
ON CONFLICT (crop_name) DO UPDATE SET
    base_temp_c = EXCLUDED.base_temp_c,
    upper_temp_c = EXCLUDED.upper_temp_c,
    total_gdd_required = EXCLUDED.total_gdd_required,
    stages = EXCLUDED.stages,
    kc_values = EXCLUDED.kc_values,
    source = EXCLUDED.source,
    updated_at = NOW();

-- Update existing crop records with GDD config linkage
UPDATE crop SET
    growing_season_days = CASE
        WHEN name ILIKE '%maize%' THEN 120
        WHEN name ILIKE '%bean%' THEN 90
        WHEN name ILIKE '%cassava%' THEN 300
        WHEN name ILIKE '%sweet potato%' THEN 150
        WHEN name ILIKE '%coffee%' THEN 240
        WHEN name ILIKE '%avocado%' THEN 180
        WHEN name ILIKE '%tomato%' THEN 80
        WHEN name ILIKE '%banana%' THEN 365
        ELSE growing_season_days
    END
WHERE growing_season_days IS NULL;

COMMIT;
