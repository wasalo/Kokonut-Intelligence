-- ============================================================
-- 234_marketplace_view_alignment.sql
-- ============================================================

CREATE OR REPLACE VIEW v_active_listings AS
SELECT
    ml.id,
    ml.title,
    ml.description,
    ml.location_id,
    ml.seller_id,
    ml.crop_id,
    c.name AS crop_name,
    ml.quantity,
    ml.unit,
    ml.quality_grade,
    ml.price_per_unit,
    ml.currency,
    ml.negotiable,
    ml.pickup_location,
    ml.latitude,
    ml.longitude,
    ml.delivery_available,
    ml.available_from,
    ml.available_until,
    ml.image_urls,
    ml.created_at,
    ml.published_at,
    l.name AS location_name
FROM market_listing ml
LEFT JOIN crop c ON c.id = ml.crop_id
LEFT JOIN location l ON l.id = ml.location_id
WHERE ml.status = 'published'
  AND ml.sold_at IS NULL
  AND (ml.expires_at IS NULL OR ml.expires_at > NOW())
ORDER BY ml.created_at DESC;
