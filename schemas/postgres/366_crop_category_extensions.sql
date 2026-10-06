-- ============================================================
-- 366_crop_category_extensions.sql
-- Document source-backed, free-text crop category extensions selected in the
-- Species Type crosswalk. This changes no crop rows and adds no value check.
-- ============================================================

BEGIN;

COMMENT ON COLUMN crop.crop_category IS
    'Free-text crop category label. Documented values include grain, legume, vegetable, fruit, root, fiber, oil, spice, tree, ornamental, utility, and other. Preserve source-backed labels through explicit crosswalks; do not infer a category from crop names.';

COMMIT;
