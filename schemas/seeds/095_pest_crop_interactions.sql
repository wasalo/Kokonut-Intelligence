-- 095_pest_crop_interactions.sql
-- Pest-crop interaction matrix for common tropical crop-pest combinations

BEGIN;

INSERT INTO pest_crop_interaction (
    pest_name, crop_name, damage_type,
    severity_by_stage, yield_loss_potential, peak_risk_stage,
    preferred_management
) VALUES
    ('fall_armyworm', 'maize', 'leaf_defoliation',
     '{"seedling":"low","vegetative":"moderate","tasseling":"high","grain_fill":"critical"}',
     50.0, 'tasseling',
     '["biological","cultural","chemical"]'),

    ('fall_armyworm', 'sorghum', 'leaf_defoliation',
     '{"seedling":"low","vegetative":"moderate","heading":"high","grain_fill":"critical"}',
     40.0, 'heading',
     '["biological","cultural","chemical"]'),

    ('fall_armyworm', 'rice', 'leaf_defoliation',
     '{"seedling":"low","tillering":"moderate","heading":"moderate","grain_fill":"high"}',
     25.0, 'heading',
     '["biological","cultural"]'),

    ('stem_borer', 'maize', 'stem_tunneling',
     '{"seedling":"low","vegetative":"moderate","tasseling":"high","grain_fill":"high"}',
     30.0, 'tasseling',
     '["biological","cultural"]'),

    ('stem_borer', 'sorghum', 'stem_tunneling',
     '{"seedling":"low","vegetative":"moderate","heading":"high","grain_fill":"high"}',
     25.0, 'heading',
     '["biological","cultural"]'),

    ('aphids', 'maize', 'sucking_sap',
     '{"seedling":"high","vegetative":"moderate","tasseling":"low","grain_fill":"low"}',
     20.0, 'seedling',
     '["biological","cultural"]'),

    ('aphids', 'beans', 'sucking_sap_virus',
     '{"seedling":"high","vegetative":"high","flowering":"critical","pod_fill":"moderate"}',
     35.0, 'flowering',
     '["biological","cultural","chemical"]'),

    ('aphids', 'tomato', 'sucking_sap_virus',
     '{"seedling":"high","vegetative":"moderate","flowering":"high","fruiting":"moderate"}',
     30.0, 'seedling',
     '["biological","cultural","chemical"]'),

    ('whitefly', 'tomato', 'sucking_sap_virus_tylcv',
     '{"seedling":"critical","vegetative":"high","flowering":"high","fruiting":"moderate"}',
     60.0, 'seedling',
     '["biological","chemical","cultural"]'),

    ('whitefly', 'cassava', 'sucking_sap_virus_cmd',
     '{"establishment":"high","vegetative":"moderate","bulking":"low"}',
     40.0, 'establishment',
     '["cultural","biological"]'),

    ('whitefly', 'beans', 'sucking_sap_virus',
     '{"seedling":"high","vegetative":"moderate","flowering":"high","pod_fill":"moderate"}',
     25.0, 'seedling',
     '["biological","chemical"]'),

    ('leafhopper', 'maize', 'virus_transmission_msv',
     '{"seedling":"critical","vegetative":"high","tasseling":"moderate","grain_fill":"low"}',
     40.0, 'seedling',
     '["cultural","chemical"]'),

    ('fruit_fruit_fly', 'mango', 'fruit_boring',
     '{"flowering":"low","fruit_set":"moderate","fruit_development":"high","ripening":"critical"}',
     60.0, 'ripening',
     '["chemical","cultural","biological"]'),

    ('fruit_fruit_fly', 'papaya', 'fruit_boring',
     '{"fruit_set":"moderate","fruit_development":"high","ripening":"critical"}',
     50.0, 'ripening',
     '["chemical","cultural"]'),

    ('red_spider_mite', 'beans', 'leaf_stippling',
     '{"seedling":"low","vegetative":"moderate","flowering":"high","pod_fill":"moderate"}',
     25.0, 'flowering',
     '["biological","chemical"]'),

    ('red_spider_mite', 'tomato', 'leaf_stippling',
     '{"vegetative":"moderate","flowering":"high","fruiting":"moderate"}',
     20.0, 'flowering',
     '["biological","chemical"]'),

    ('late_blight', 'tomato', 'leaf_fruit_rot',
     '{"vegetative":"moderate","flowering":"high","fruiting":"critical"}',
     70.0, 'fruiting',
     '["chemical","biological","cultural"]'),

    ('late_blight', 'potato', 'leaf_tuber_rot',
     '{"vegetative":"moderate","tuber_formation":"high","bulking":"critical"}',
     60.0, 'bulking',
     '["chemical","biological","cultural"]'),

    ('powdery_mildew', 'cucurbits', 'leaf_powdery',
     '{"seedling":"low","vegetative":"moderate","flowering":"high","fruiting":"high"}',
     30.0, 'flowering',
     '["chemical","biological","cultural"]'),

    ('rust_puccinia', 'beans', 'leaf_pustules',
     '{"vegetative":"moderate","flowering":"high","pod_fill":"critical"}',
     40.0, 'pod_fill',
     '["chemical","cultural"]'),

    ('rust_puccinia', 'coffee', 'leaf_pustules',
     '{"vegetative":"low","flowering":"moderate","berry_development":"high"}',
     25.0, 'berry_development',
     '["chemical","cultural"]'),

    ('root_knot_nematode', 'tomato', 'root_galling',
     '{"seedling":"high","vegetative":"high","flowering":"moderate","fruiting":"low"}',
     45.0, 'seedling',
     '["cultural","biological"]'),

    ('striga', 'maize', 'root_parasitism',
     '{"seedling":"high","vegetative":"high","tasseling":"moderate","grain_fill":"low"}',
     50.0, 'vegetative',
     '["cultural","chemical"]'),

    ('striga', 'sorghum', 'root_parasitism',
     '{"seedling":"high","vegetative":"high","heading":"moderate","grain_fill":"low"}',
     45.0, 'vegetative',
     '["cultural","chemical"]'),

    ('bollworm', 'cotton', 'boll_boring',
     '{"vegetative":"low","flowering":"moderate","boll_formation":"high","boll_development":"critical"}',
     55.0, 'boll_development',
     '["biological","chemical","cultural"]'),

    ('bollworm', 'tomato', 'fruit_boring',
     '{"vegetative":"low","flowering":"high","fruiting":"critical"}',
     45.0, 'fruiting',
     '["biological","chemical"]'),

    ('shoot_fly', 'maize', 'dead_heart',
     '{"seedling":"critical","vegetative":"high","tasseling":"low","grain_fill":"low"}',
     35.0, 'seedling',
     '["cultural","biological"]'),

    ('shoot_fly', 'sorghum', 'dead_heart',
     '{"seedling":"critical","vegetative":"high","heading":"low","grain_fill":"low"}',
     30.0, 'seedling',
     '["cultural","biological"]'),

    ('termites', 'maize', 'root_stem_feeding',
     '{"seedling":"high","vegetative":"high","tasseling":"moderate","grain_fill":"moderate"}',
     40.0, 'seedling',
     '["chemical","cultural"]'),

    ('termites', 'cassava', 'root_feeding',
     '{"establishment":"high","vegetative":"moderate","bulking":"low"}',
     30.0, 'establishment',
     '["cultural","chemical"]'),

    ('maize_weevil', 'maize', 'storage_damage',
     '{"harvest":"low","drying":"moderate","storage":"critical"}',
     30.0, 'storage',
     '["cultural","chemical"]'),

    ('bacterial_wilt', 'cucurbits', 'vascular_wilting',
     '{"seedling":"critical","vegetative":"high","flowering":"moderate","fruiting":"low"}',
     55.0, 'seedling',
     '["cultural","biological"]'),

    ('parthenium', 'maize', 'weed_competition',
     '{"seedling":"moderate","vegetative":"high","tasseling":"high","grain_fill":"moderate"}',
     35.0, 'vegetative',
     '["biological","cultural"]'),

    ('legume_pod_borer', 'beans', 'pod_boring',
     '{"vegetative":"low","flowering":"high","pod_fill":"critical"}',
     40.0, 'pod_fill',
     '["biological","chemical","cultural"]'),

    ('maize_chlorotic_mottle', 'maize', 'viral_mottle',
     '{"seedling":"high","vegetative":"high","tasseling":"high","grain_fill":"high"}',
     50.0, 'vegetative',
     '["cultural","chemical"]'),

    ('leaf_beetle', 'beans', 'defoliation',
     '{"seedling":"high","vegetative":"moderate","flowering":"low","pod_fill":"low"}',
     20.0, 'seedling',
     '["biological","cultural"]')

ON CONFLICT (pest_name, crop_name) DO UPDATE SET
    damage_type = EXCLUDED.damage_type,
    severity_by_stage = EXCLUDED.severity_by_stage,
    yield_loss_potential = EXCLUDED.yield_loss_potential,
    peak_risk_stage = EXCLUDED.peak_risk_stage,
    preferred_management = EXCLUDED.preferred_management;

COMMIT;
