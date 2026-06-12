-- ============================================================
-- Seed: Expense Categories
-- ============================================================

INSERT INTO expense_category (name, code, is_direct, sort_order) VALUES
    ('Seeds & Planting Material', 'SEED', true, 1),
    ('Fertilizer & Soil Amendments', 'FERT', true, 2),
    ('Pest & Disease Control', 'PEST', true, 3),
    ('Irrigation & Water', 'IRRI', true, 4),
    ('Labor - Field', 'LAB-F', true, 5),
    ('Labor - Processing', 'LAB-P', true, 6),
    ('Labor - Admin', 'LAB-A', false, 7),
    ('Equipment & Machinery', 'EQUI', true, 8),
    ('Transport & Logistics', 'TRAN', true, 9),
    ('Packaging & Processing', 'PACK', true, 10),
    ('Utilities', 'UTIL', false, 11),
    ('Rent & Land', 'RENT', false, 12),
    ('Insurance', 'INS', false, 13),
    ('Marketing & Sales', 'MARK', false, 14),
    ('Professional Services', 'PROF', false, 15),
    ('Maintenance & Repairs', 'MAINT', true, 16),
    ('Bioinputs & Compost', 'BIO', true, 17),
    ('Other Direct Costs', 'OTH-D', true, 18),
    ('Other Shared Costs', 'OTH-S', false, 19)
ON CONFLICT (name) DO NOTHING;
