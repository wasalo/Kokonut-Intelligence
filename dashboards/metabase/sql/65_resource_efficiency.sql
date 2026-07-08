-- Dashboard SQL: 65_resource_efficiency
-- Labor, energy, and water efficiency per kilogram of yield by crop

SELECT
    rc.location_id,
    l.name AS location_name,
    rc.resource_type,
    rc.unit,
    rc.component,
    cc.cycle_name,
    c.name AS crop_name,
    SUM(rc.quantity) AS total_quantity,
    AVG(rc.quantity) AS avg_per_period,
    COUNT(*) AS record_count,
    SUM(CASE WHEN rc.is_estimated THEN 1 ELSE 0 END) AS estimated_count,
    SUM(he.quantity) AS total_harvest_kg,
    CASE
        WHEN SUM(he.quantity) > 0
        THEN ROUND(SUM(rc.quantity) / SUM(he.quantity), 4)
        ELSE NULL
    END AS quantity_per_kg_yield
FROM resource_consumption rc
JOIN location l ON l.id = rc.location_id
LEFT JOIN crop_cycle cc ON cc.id = rc.crop_cycle_id
LEFT JOIN crop c ON c.id = cc.crop_id
LEFT JOIN harvest_event he ON he.crop_cycle_id = rc.crop_cycle_id
    AND he.status IN ('verified', 'published')
WHERE rc.status IN ('verified', 'published')
  AND l.status = 'active'
GROUP BY
    rc.location_id, l.name, rc.resource_type, rc.unit, rc.component,
    cc.cycle_name, c.name
ORDER BY rc.resource_type, total_quantity DESC;
