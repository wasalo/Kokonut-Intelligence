-- Eagle View: Crop Diversity by Season
-- Number of crop cycles and unique crops per season per plot

SELECT
    cc.season,
    p.name AS plot_name,
    l.name AS location_name,
    COUNT(*) AS cycle_count,
    COUNT(DISTINCT c.name) AS unique_crops,
    STRING_AGG(DISTINCT c.name, ', ' ORDER BY c.name) AS crop_list
FROM crop_cycle cc
JOIN crop c ON cc.crop_id = c.id
JOIN plot p ON cc.plot_id = p.id
JOIN location l ON cc.location_id = l.id
WHERE cc.season IS NOT NULL
GROUP BY cc.season, p.name, l.name
ORDER BY cc.season ASC, p.name;
