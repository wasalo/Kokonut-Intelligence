-- 093_pest_biology_reference.sql
-- Reference data for 25+ tropical pests: lifecycle parameters, host crops, natural enemies

BEGIN;

INSERT INTO pest_biology_reference (
    pest_name, scientific_name, common_name, pest_category,
    base_temp, upper_temp, total_degree_days, stages,
    host_crops, natural_enemies,
    damage_description, economic_importance, geographic_range
) VALUES
    -- Lepidoptera
    ('fall_armyworm', 'Spodoptera frugiperda', 'Fall Armyworm', 'insect',
     10.0, 38.0, 550.0,
     '[{"name":"egg","dd_start":0,"dd_end":30},{"name":"larva","dd_start":30,"dd_end":350},{"name":"pupa","dd_start":350,"dd_end":430},{"name":"adult","dd_start":430,"dd_end":550}]',
     '["maize","sorghum","rice","millet","cotton","soybean"]',
     '[{"name":"Trichogramma spp.","type":"parasitoid","effectiveness":"high"},{"name":"Cotesia flavipes","type":"parasitoid","effectiveness":"moderate"},{"name":"Beauveria bassiana","type":"pathogen","effectiveness":"moderate"},{"name":"Chrysoperla carnea","type":"predator","effectiveness":"moderate"}]',
     'Larvae feed on leaves, whorl, and ear; can cause 100% yield loss in maize if uncontrolled',
     'critical', 'Sub-Saharan Africa, South Asia, Southeast Asia, Americas'),

    ('stem_borer', 'Busseola fusca', 'Maize Stem Borer', 'insect',
     10.0, 35.0, 600.0,
     '[{"name":"egg","dd_start":0,"dd_end":40},{"name":"larva","dd_start":40,"dd_end":400},{"name":"pupa","dd_start":400,"dd_end":480},{"name":"adult","dd_start":480,"dd_end":600}]',
     '["maize","sorghum","millet","sugarcane"]',
     '[{"name":"Cotesia flavipes","type":"parasitoid","effectiveness":"high"},{"name":"Dolichogenidea spp.","type":"parasitoid","effectiveness":"moderate"}]',
     'Larvae bore into stems causing dead hearts and white heads; 10-30% yield loss typical',
     'high', 'Sub-Saharan Africa, South Asia'),

    ('fall_armyworm_rice', 'Spodoptera frugiperda', 'Fall Armyworm (Rice)', 'insect',
     10.0, 38.0, 550.0,
     '[{"name":"egg","dd_start":0,"dd_end":30},{"name":"larva","dd_start":30,"dd_end":350},{"name":"pupa","dd_start":350,"dd_end":430},{"name":"adult","dd_start":430,"dd_end":550}]',
     '["rice"]',
     '[{"name":"Trichogramma spp.","type":"parasitoid","effectiveness":"moderate"}]',
     'Larvae feed on rice leaves and tillers; lower damage potential than on maize',
     'moderate', 'Sub-Saharan Africa, South Asia'),

    -- Hemiptera
    ('aphids', 'Aphis gossypii', 'Cotton/Melon Aphid', 'insect',
     5.0, 32.0, 120.0,
     '[{"name":"nymph","dd_start":0,"dd_end":80},{"name":"adult","dd_start":80,"dd_end":120}]',
     '["maize","beans","tomato","cotton","cucurbits"]',
     '[{"name":"Lady beetles (Coccinellidae)","type":"predator","effectiveness":"high"},{"name":"Lacewings (Chrysoperla)","type":"predator","effectiveness":"high"},{"name":"Aphidius spp.","type":"parasitoid","effectiveness":"high"},{"name":"Hoverflies (Syrphidae)","type":"predator","effectiveness":"moderate"}]',
     'Sucking insects causing leaf curling, yellowing, and virus transmission; honeydew promotes sooty mould',
     'high', 'Worldwide in tropical and temperate regions'),

    ('whitefly', 'Bemisia tabaci', 'Sweetpotato Whitefly', 'insect',
     11.0, 35.0, 300.0,
     '[{"name":"egg","dd_start":0,"dd_end":50},{"name":"nymph","dd_start":50,"dd_end":220},{"name":"pupa","dd_start":220,"dd_end":270},{"name":"adult","dd_start":270,"dd_end":300}]',
     '["tomato","cassava","beans","cucurbits","cotton"]',
     '[{"name":"Encarsia formosa","type":"parasitoid","effectiveness":"high"},{"name":"Eretmocerus eremicus","type":"parasitoid","effectiveness":"moderate"},{"name":"Beauveria bassiana","type":"pathogen","effectiveness":"moderate"}]',
     'Vectors Tomato Yellow Leaf Curl Virus (TYLCV) and Cassava Mosaic Disease; direct feeding causes wilting',
     'critical', 'Worldwide tropical and subtropical'),

    ('leafhopper', 'Cicadulina mbila', 'Maize Leafhopper', 'insect',
     10.0, 35.0, 180.0,
     '[{"name":"nymph","dd_start":0,"dd_end":100},{"name":"adult","dd_start":100,"dd_end":180}]',
     '["maize","sorghum","millet"]',
     '[{"name":"Paranagyrus spp.","type":"parasitoid","effectiveness":"moderate"}]',
     'Vectors Maize Streak Virus; causes chlorotic streaks reducing photosynthesis',
     'high', 'Sub-Saharan Africa'),

    -- Diptera
    ('fruit_fruit_fly', 'Bactrocera dorsalis', 'Oriental Fruit Fly', 'insect',
     12.0, 36.0, 400.0,
     '[{"name":"egg","dd_start":0,"dd_end":15},{"name":"larva","dd_start":15,"dd_end":250},{"name":"pupa","dd_start":250,"dd_end":350},{"name":"adult","dd_start":350,"dd_end":400}]',
     '["mango","papaya","guava","citrus","avocado"]',
     '[{"name":"Fopius arisanus","type":"parasitoid","effectiveness":"high"},{"name":"Psyttalia spp.","type":"parasitoid","effectiveness":"moderate"}]',
     'Larvae bore into fruits causing rot and premature drop; 20-80% fruit loss possible',
     'critical', 'Sub-Saharan Africa, South Asia, Southeast Asia'),

    -- Coleoptera
    ('maize_weevil', 'Sitophilus zeamais', 'Maize Weevil', 'insect',
     13.0, 34.0, 450.0,
     '[{"name":"egg","dd_start":0,"dd_end":30},{"name":"larva","dd_start":30,"dd_end":280},{"name":"pupa","dd_start":280,"dd_end":330},{"name":"adult","dd_start":330,"dd_end":450}]',
     '["maize","rice","sorghum","millet"]',
     '[{"name":"Theocolax formiciformis","type":"parasitoid","effectiveness":"moderate"},{"name":"Holepyris spp.","type":"parasitoid","effectiveness":"moderate"}]',
     'Larvae develop inside kernels; adults bore exit holes; 10-35% post-harvest loss',
     'high', 'Worldwide tropical and subtropical'),

    ('bean_dry_bean_beetle', 'Acanthoscelides obtectus', 'Dry Bean Beetle', 'insect',
     10.0, 33.0, 350.0,
     '[{"name":"egg","dd_start":0,"dd_end":20},{"name":"larva","dd_start":20,"dd_end":220},{"name":"pupa","dd_start":220,"dd_end":280},{"name":"adult","dd_start":280,"dd_end":350}]',
     '["beans","cowpeas"]',
     '[{"name":"Stilboccala spp.","type":"parasitoid","effectiveness":"low"}]',
     'Larvae feed on bean seeds in storage; 20-50% post-harvest loss',
     'high', 'Sub-Saharan Africa, Latin America'),

    -- Mites
    ('red_spider_mite', 'Tetranychus urticae', 'Two-Spotted Spider Mite', 'mite',
     12.0, 40.0, 200.0,
     '[{"name":"egg","dd_start":0,"dd_end":20},{"name":"larva","dd_start":20,"dd_end":80},{"name":"nymph","dd_start":80,"dd_end":140},{"name":"adult","dd_start":140,"dd_end":200}]',
     '["beans","tomato","cucurbits","fruit_trees"]',
     '[{"name":"Phytoseiulus persimilis","type":"predator","effectiveness":"high"},{"name":"Neoseiulus californicus","type":"predator","effectiveness":"high"},{"name":"Stethorus spp.","type":"predator","effectiveness":"moderate"}]',
     'Sucking mites causing leaf stippling, bronzing, and webbing; severe infestations cause defoliation',
     'moderate', 'Worldwide'),

    -- Nematodes
    ('root_knot_nematode', 'Meloidogyne incognita', 'Root-Knot Nematode', 'nematode',
     15.0, 35.0, NULL,
     '[{"name":"juvenile","dd_start":0,"dd_end":NULL},{"name":"adult","dd_start":NULL,"dd_end":NULL}]',
     '["tomato","beans","maize","cucurbits","vegetables"]',
     '[{"name":"Pasteuria penetrans","type":"pathogen","effectiveness":"moderate"},{"name":"Purpureocillium lilacinum","type":"pathogen","effectiveness":"low"}]',
     'Root galling reduces nutrient and water uptake; stunting, yellowing, wilting',
     'high', 'Worldwide tropical and subtropical'),

    -- Fungal diseases
    ('late_blight', 'Phytophthora infestans', 'Late Blight', 'fungal',
     7.0, 30.0, NULL,
     '[{"name":"infection","dd_start":0,"dd_end":NULL},{"name":"sporulation","dd_start":NULL,"dd_end":NULL}]',
     '["tomato","potato"]',
     '[{"name":"Bacillus subtilis","type":"antagonist","effectiveness":"moderate"},{"name":"Trichoderma spp.","type":"antagonist","effectiveness":"moderate"}]',
     'Rapid leaf lesions, stem lesions, and fruit rot; can destroy entire crop in days under favorable conditions',
     'critical', 'Worldwide in cool, wet conditions'),

    ('powdery_mildew', 'Erysiphe cichoracearum', 'Powdery Mildew', 'fungal',
     10.0, 35.0, NULL,
     '[{"name":"infection","dd_start":0,"dd_end":NULL}]',
     '["cucurbits","tomato","beans","maize"]',
     '[{"name":"Ampelomyces quisqualis","type":"hyperparasite","effectiveness":"moderate"},{"name":"Bacillus pumilus","type":"antagonist","effectiveness":"moderate"}]',
     'White powdery leaf spots reduce photosynthesis; premature leaf drop',
     'moderate', 'Worldwide'),

    ('rust_puccinia', 'Puccinia spp.', 'Rust', 'fungal',
     8.0, 30.0, NULL,
     '[{"name":"infection","dd_start":0,"dd_end":NULL},{"name":"sporulation","dd_start":NULL,"dd_end":NULL}]',
     '["maize","beans","coffee","wheat"]',
     '[{"name":"Ampelomyces quisqualis","type":"hyperparasite","effectiveness":"low"}]',
     'Pustules on leaves and stems reduce yield; severe infections cause premature death',
     'high', 'Worldwide'),

    ('bacterial_wilt', 'Erwinia tracheiphila', 'Bacterial Wilt', 'bacterial',
     15.0, 35.0, NULL,
     '[{"name":"incubation","dd_start":0,"dd_end":NULL}]',
     '["cucurbits","banana","tomato"]',
     '[{"name":"Bacteriophages","type":"antagonist","effectiveness":"low"}]',
     'Bacteria block xylem causing rapid wilting; often fatal',
     'high', 'Americas, Africa'),

    ('cassava_mosaic', 'Cassava Mosaic Virus', 'Cassava Mosaic Disease', 'viral',
     15.0, 35.0, NULL,
     '[{"name":"incubation","dd_start":0,"dd_end":NULL}]',
     '["cassava"]',
     '[{"name":"None (vector control only)","type":"none","effectiveness":"none"}]',
     'Mosaic pattern on leaves reduces photosynthesis; severe stunting and yield loss',
     'critical', 'Sub-Saharan Africa, South Asia'),

    -- Weeds
    ('striga', 'Striga hermonthica', 'Witchweed', 'weed',
     18.0, 38.0, NULL,
     '[{"name":"germination","dd_start":0,"dd_end":NULL},{"name":"attachment","dd_start":NULL,"dd_end":NULL}]',
     '["maize","sorghum","millet","rice"]',
     '[{"name":"Fusarium oxysporum","type":"pathogen","effectiveness":"moderate"},{"name":"Striga-specific herbicides","type":"chemical","effectiveness":"high"}]',
     'Parasitic weed attaches to roots causing stunting, yellowing, and severe yield loss',
     'critical', 'Sub-Saharan Africa'),

    ('parthenium', 'Parthenium hysterophorus', 'Parthenium Weed', 'weed',
     10.0, 40.0, NULL,
     '[{"name":"germination","dd_start":0,"dd_end":NULL},{"name":"flowering","dd_start":NULL,"dd_end":NULL}]',
     '["maize","sorghum","cotton","vegetables"]',
     '[{"name":"Zygogramma bicolorata","type":"predator","effectiveness":"high"},{"name":"Prospalangia spp.","type":"parasitoid","effectiveness":"moderate"}]',
     'Aggressive invasive weed competing for nutrients, water, and light; allelopathic to crops',
     'high', 'South Asia, Africa, Australia'),

    -- Rodents
    ('field_rats', 'Rattus rattus', 'Black Rat', 'rodent',
     NULL, NULL, NULL,
     '[]',
     '["maize","rice","cassava","stored grain"]',
     '[{"name":"Owls (Tyto alba)","type":"predator","effectiveness":"high"},{"name":"Mongooses","type":"predator","effectiveness":"moderate"}]',
     'Rods and grain feed on crops; can cause 5-30% field loss and 10-40% storage loss',
     'high', 'Worldwide'),

    -- Additional insects
    ('bollworm', 'Helicoverpa armigera', 'Cotton Bollworm', 'insect',
     10.0, 35.0, 520.0,
     '[{"name":"egg","dd_start":0,"dd_end":25},{"name":"larva","dd_start":25,"dd_end":320},{"name":"pupa","dd_start":320,"dd_end":420},{"name":"adult","dd_start":420,"dd_end":520}]',
     '["cotton","tomato","chickpea","maize"]',
     '[{"name":"Trichogramma spp.","type":"parasitoid","effectiveness":"high"},{"name":"Cotesia spp.","type":"parasitoid","effectiveness":"moderate"},{"name":"Chrysoperla carnea","type":"predator","effectiveness":"moderate"}]',
     'Larvae bore into buds, flowers, and bolls/fruits; major constraint on cotton and tomato',
     'critical', 'Worldwide'),

    ('shoot_fly', 'Atherigona soccata', 'Maize Shoot Fly', 'insect',
     12.0, 35.0, 300.0,
     '[{"name":"egg","dd_start":0,"dd_end":15},{"name":"larva","dd_start":15,"dd_end":180},{"name":"pupa","dd_start":180,"dd_end":240},{"name":"adult","dd_start":240,"dd_end":300}]',
     '["maize","sorghum","millet"]',
     '[{"name":"Trichogramma spp.","type":"parasitoid","effectiveness":"moderate"}]',
     'Larvae cut the growing point causing dead heart; early season damage is most severe',
     'high', 'Sub-Saharan Africa, South Asia'),

    ('termites', 'Macrotermes spp.', 'Termites', 'insect',
     15.0, 40.0, NULL,
     '[{"name":"nymph","dd_start":0,"dd_end":NULL},{"name":"adult","dd_start":NULL,"dd_end":NULL}]',
     '["maize","sorghum","cassava","sugarcane","fruit_trees"]',
     '[{"name":"Entomopathogenic fungi (Metarhizium)","type":"pathogen","effectiveness":"moderate"}]',
     'Build mounds and feed on plant material; can cause complete crop loss in severe infestations',
     'high', 'Sub-Saharan Africa, South Asia'),

    ('leaf_beetle', 'Ootheca mutabilis', 'Bean Leaf Beetle', 'insect',
     10.0, 33.0, 280.0,
     '[{"name":"egg","dd_start":0,"dd_end":30},{"name":"larva","dd_start":30,"dd_end":180},{"name":"pupa","dd_start":180,"dd_end":220},{"name":"adult","dd_start":220,"dd_end":280}]',
     '["beans","cowpeas"]',
     '[{"name":"Coccinella spp.","type":"predator","effectiveness":"moderate"}]',
     'Adults defoliate leaves and feed on flowers/pods; larvae feed on roots',
     'moderate', 'Sub-Saharan Africa'),

    ('legume_pod_borer', 'Maruca vitrata', 'Legume Pod Borer', 'insect',
     10.0, 35.0, 400.0,
     '[{"name":"egg","dd_start":0,"dd_end":20},{"name":"larva","dd_start":20,"dd_end":250},{"name":"pupa","dd_start":250,"dd_end":320},{"name":"adult","dd_start":320,"dd_end":400}]',
     '["beans","cowpeas","pigeon pea"]',
     '[{"name":"Trichogramma spp.","type":"parasitoid","effectiveness":"moderate"},{"name":"Bracon spp.","type":"parasitoid","effectiveness":"moderate"}]',
     'Larvae web and feed on flowers, pods, and leaves; major constraint on legume production',
     'high', 'Sub-Saharan Africa, South Asia'),

    ('maize_chlorotic_mottle', 'Maize Chlorotic Mottle Virus', 'Maize Chlorotic Mottle Virus', 'viral',
     15.0, 35.0, NULL,
     '[{"name":"incubation","dd_start":0,"dd_end":NULL}]',
     '["maize"]',
     '[{"name":"None (vector control only)","type":"none","effectiveness":"none"}]',
     'Chlorotic mottle on leaves; combined with Maize Lethal Necrosis causes 100% yield loss',
     'critical', 'Sub-Saharan Africa'),

    ('banana_xanthomonas', 'Xanthomonas campestris pv. musacearum', 'Xanthomonas Wilt', 'bacterial',
     18.0, 35.0, NULL,
     '[{"name":"incubation","dd_start":0,"dd_end":NULL}]',
     '["banana","enset"]',
     '[{"name":"None (sanitation only)","type":"none","effectiveness":"none"}]',
     'Wilting, yellowing, and rapid plant death; spread by contaminated tools and insects',
     'critical', 'Sub-Saharan Africa'),

    ('maize_streak', 'Maize Streak Virus', 'Maize Streak Disease', 'viral',
     12.0, 35.0, NULL,
     '[{"name":"incubation","dd_start":0,"dd_end":NULL}]',
     '["maize","sorghum","millet"]',
     '[{"name":"None (vector control only)","type":"none","effectiveness":"none"}]',
     'Chlorotic streaks on leaves reduce photosynthesis; severe infections cause stunting',
     'high', 'Sub-Saharan Africa')

ON CONFLICT (pest_name) DO UPDATE SET
    scientific_name = EXCLUDED.scientific_name,
    common_name = EXCLUDED.common_name,
    pest_category = EXCLUDED.pest_category,
    base_temp = EXCLUDED.base_temp,
    upper_temp = EXCLUDED.upper_temp,
    total_degree_days = EXCLUDED.total_degree_days,
    stages = EXCLUDED.stages,
    host_crops = EXCLUDED.host_crops,
    natural_enemies = EXCLUDED.natural_enemies,
    damage_description = EXCLUDED.damage_description,
    economic_importance = EXCLUDED.economic_importance,
    geographic_range = EXCLUDED.geographic_range,
    updated_at = NOW();

COMMIT;
