-- 094_pest_mode_of_action.sql
-- IRAC, FRAC, HRAC mode of action codes for common pesticide classes

BEGIN;

INSERT INTO pest_mode_of_action (
    chemical_class, moa_code, irac_group, frac_group, hrac_group,
    mode_of_action, cross_resistance, rotation_compatibility
) VALUES
    -- Insecticides (IRAC groups)
    ('organophosphate', '1A', '1 - Acetylcholinesterase inhibitors', NULL, NULL,
     'Acetylcholinesterase inhibition; broad-spectrum nerve agent',
     '["1B"]', '["3A","4A","5","11","13","28"]'),

    ('carbamate', '1B', '1 - Acetylcholinesterase inhibitors', NULL, NULL,
     'Reversible acetylcholinesterase inhibition; broad-spectrum',
     '["1A"]', '["3A","4A","5","11","13","28"]'),

    ('pyrethroid', '3A', '3 - Sodium channel modulators', NULL, NULL,
     'Sodium channel modulation causing prolonged nerve depolarization',
     '["3B"]', '["1A","1B","4A","5","11","13","28"]'),

    ('pyrethroid_ii', '3B', '3 - Sodium channel modulators', NULL, NULL,
     'Type II pyrethroids: sodium channel modulation with longer knockdown',
     '["3A"]', '["1A","1B","4A","5","11","13","28"]'),

    ('neonicotinoid', '4A', '4 - Nicotinic acetylcholine receptor agonists', NULL, NULL,
     'Nicotinic acetylcholine receptor agonism; systemic activity',
     '["4B","4C","4D"]', '["1A","1B","3A","5","11","13","28"]'),

    ('spinosyn', '5', '5 - Nicotinic acetylcholine receptor allosteric modulators', NULL, NULL,
     'Allosteric modulation of nicotinic acetylcholine receptors',
     '[]', '["1A","1B","3A","4A","11","13","28"]'),

    ('diamide', '28', '28 - Ryanodine receptor modulators', NULL, NULL,
     'Ryanodine receptor activation causing muscle paralysis',
     '[]', '["1A","1B","3A","4A","5","11","13"]'),

    (' avermectin', '6', '6 - Glutamate-gated chloride channel allosteric modulators', NULL, NULL,
     'Glutamate-gated chloride channel modulation; systemic',
     '[]', '["1A","1B","3A","4A","5","11","13","28"]'),

    ('btk', '11A', '11 - Microbial disruptors of insect midgut membranes', NULL, NULL,
     'Cry protein crystal disruption of larval midgut; highly specific',
     '[]', '["1A","1B","3A","4A","5","13","28"]'),

    ('neem_azadirachtin', '18', '18 - Insect growth regulators (IGRs)', NULL, NULL,
     'Ecdysone antagonist disrupting molting and development',
     '[]', '["1A","1B","3A","4A","5","11","28"]'),

    ('pyriproxyfen', '7C', '7 - Juvenile hormone mimics', NULL, NULL,
     'Juvenile hormone analog preventing adult development',
     '[]', '["1A","1B","3A","4A","5","11","28"]'),

    ('diflubenzuron', '15A', '15 - Chitin synthesis inhibitors', NULL, NULL,
     'Chitin synthesis inhibition preventing cuticle formation',
     '["15B","15C"]', '["1A","1B","3A","4A","5","11","28"]'),

    -- Fungicides (FRAC groups)
    ('chlorothalonil', 'M05', NULL, 'M05 - Multi-site activity', NULL,
     'Multi-site contact fungicide; protectant mode of action',
     '[]', '["3","4","9","11","13","17"]'),

    ('mancozeb', 'M03', NULL, 'M03 - Multi-site activity', NULL,
     'Multi-site contact fungicide; protectant with some systemic uptake',
     '[]', '["3","4","9","11","13","17"]'),

    ('metalaxyl', '4', NULL, '4 - Phenylamide', NULL,
     'RNA polymerase I inhibitor; systemic and curative',
     '["4 (resistance common)"]', '["3","9","11","13","M03","M05"]'),

    ('triazole', '3', NULL, '3 - Demethylation inhibitors (DMI)', NULL,
     'C-14 demethylation inhibition in ergosterol biosynthesis',
     '["3 (cross-resistance within triazoles)"]', '["4","9","11","13","M03","M05"]'),

    ('strobilurin', '11', NULL, '11 - QoI (respiration inhibitors)', NULL,
     'Cytochrome bc1 complex inhibition at Qo site',
     '["11 (cross-resistance within strobilurins)"]', '["3","4","9","13","M03","M05"]'),

    ('carboxamide', '7', NULL, '7 - SDHI (succinate dehydrogenase inhibitors)', NULL,
     'Succinate dehydrogenase inhibition in mitochondrial complex II',
     '["7 (cross-resistance within SDHIs)"]', '["3","4","9","11","13","M03","M05"]'),

    ('biological_fungicide', 'BM02', NULL, 'BM02 - Microbial', NULL,
     'Microbial antagonists and competitive exclusion',
     '[]', '["3","4","9","11","13","M03","M05"]'),

    -- Herbicides (HRAC groups)
    ('glyphosate', '9', NULL, NULL, '9 - EPSP synthase inhibitors',
     '5-enolpyruvylshikimate-3-phosphate synthase inhibition',
     '[]', '["1","2","4","6","14","15","27"]'),

    ('glufosinate', '10', NULL, NULL, '10 - Glutamine synthetase inhibitors',
     'Glutamine synthetase inhibition causing ammonia accumulation',
     '[]', '["1","2","4","6","14","15","27"]'),

    ('atrazine', '5', NULL, NULL, '5 - Photosystem II inhibitors',
     'Photosystem II electron transport inhibition',
     '["5 (cross-resistance within PSII inhibitors)"]', '["1","2","4","6","9","14","15","27"]'),

    ('2_4_d', '4', NULL, NULL, '4 - Synthetic auxins',
     'Synthetic auxin mimicking indole-3-acetic acid activity',
     '["4 (cross-resistance within synthetic auxins)"]', '["1","2","5","6","9","14","15","27"]'),

    ('pendimethalin', '3', NULL, NULL, '3 - Microtubule assembly inhibitors',
     'Microtubule assembly inhibition in dividing cells',
     '["3 (cross-resistance within dinitroanilines)"]', '["1","2","4","5","6","9","14","15","27"]'),

    ('imazapyr', '2', NULL, NULL, '2 - ALS/acetolactate synthase inhibitors',
     'Acetolactate synthase inhibition blocking branched-chain amino acid synthesis',
     '["2 (cross-resistance within ALS inhibitors)"]', '["1","3","4","5","6","9","14","15","27"]')

ON CONFLICT (chemical_class) DO UPDATE SET
    moa_code = EXCLUDED.moa_code,
    irac_group = EXCLUDED.irac_group,
    frac_group = EXCLUDED.frac_group,
    hrac_group = EXCLUDED.hrac_group,
    mode_of_action = EXCLUDED.mode_of_action,
    cross_resistance = EXCLUDED.cross_resistance,
    rotation_compatibility = EXCLUDED.rotation_compatibility;

COMMIT;
