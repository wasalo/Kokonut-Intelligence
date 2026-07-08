-- 066_ecosystem_landscape.sql
-- Ecosystem Landscape: Farm Network Visualization + Fund Farm CTA

BEGIN;

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Network map data: one row per location with spatial and funding info
CREATE OR REPLACE VIEW v_ecosystem_farm_network AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    l.country,
    l.region,
    l.latitude,
    l.longitude,
    ST_AsGeoJSON(l.center, 6) AS center_geojson,
    ST_AsGeoJSON(l.boundary, 6) AS boundary_geojson,
    (SELECT COUNT(*)::int FROM farm f WHERE f.location_id = l.id AND f.status = 'active') AS farm_count,
    (SELECT COALESCE(SUM(f.total_area), 0) FROM farm f WHERE f.location_id = l.id AND f.status = 'active') AS total_area_ha,
    (SELECT COUNT(*)::int FROM tree_record t WHERE t.location_id = l.id AND t.status = 'alive') AS tree_count,
    (SELECT COUNT(DISTINCT t.species_name) FROM tree_record t WHERE t.location_id = l.id AND t.status = 'alive') AS species_count,
    (SELECT COUNT(*)::int FROM funding_campaign fc WHERE fc.location_id = l.id AND fc.status = 'active') AS active_campaigns,
    (SELECT COALESCE(SUM(d.amount), 0) FROM donation d WHERE d.location_id = l.id AND d.status = 'completed') AS total_raised,
    l.status
FROM location l
WHERE l.status IN ('active', 'verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

-- Per-farm detail with financial and campaign data
CREATE OR REPLACE VIEW v_ecosystem_farm_detail AS
SELECT
    f.id AS farm_id,
    f.location_id,
    l.name AS location_name,
    f.name AS farm_name,
    f.farm_type,
    f.total_area,
    f.area_unit,
    ST_AsGeoJSON(f.center, 6) AS center_geojson,
    ST_AsGeoJSON(f.boundary, 6) AS boundary_geojson,
    (SELECT COUNT(*)::int FROM plot p WHERE p.farm_id = f.id AND p.status = 'active') AS plot_count,
    (SELECT COUNT(*)::int FROM tree_record t WHERE t.location_id = l.id AND t.status = 'alive') AS tree_count,
    (SELECT COUNT(DISTINCT t.species_name) FROM tree_record t WHERE t.location_id = l.id AND t.status = 'alive') AS species_count,
    (SELECT COUNT(*)::int FROM crop_cycle cc WHERE cc.plot_id IN (SELECT p.id FROM plot p WHERE p.farm_id = f.id) AND cc.status IN ('active', 'flowering', 'harvesting')) AS active_crop_cycles,
    (SELECT MAX(he.harvest_date) FROM harvest_event he WHERE he.plot_id IN (SELECT p.id FROM plot p WHERE p.farm_id = f.id)) AS last_harvest_date,
    (SELECT COALESCE(SUM(re.amount_usd), 0) FROM revenue_event re WHERE re.location_id = l.id AND re.status IN ('verified', 'published')) AS total_revenue,
    (SELECT COALESCE(SUM(ee.amount), 0) FROM expense_event ee WHERE ee.location_id = l.id AND ee.status IN ('verified', 'published')) AS total_expenses,
    f.status
FROM farm f
JOIN location l ON f.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND f.status = 'active';

-- Per-farm funding page data
CREATE OR REPLACE VIEW v_farm_funding_page AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    l.country,
    l.region,
    l.latitude,
    l.longitude,
    fr.project_summary,
    fr.local_problem,
    fr.proposed_solution,
    (SELECT COUNT(*)::int FROM funding_campaign fc WHERE fc.location_id = l.id AND fc.status = 'active') AS active_campaigns,
    (SELECT COALESCE(SUM(fc.goal_amount), 0) FROM funding_campaign fc WHERE fc.location_id = l.id AND fc.status IN ('active', 'funded')) AS total_goal,
    (SELECT COALESCE(SUM(fc.raised_amount), 0) FROM funding_campaign fc WHERE fc.location_id = l.id AND fc.status IN ('active', 'funded')) AS total_raised,
    (SELECT COUNT(DISTINCT d.id) FROM donation d WHERE d.location_id = l.id AND d.status = 'completed') AS donor_count,
    (SELECT COUNT(*)::int FROM tree_record t WHERE t.location_id = l.id AND t.status = 'alive') AS tree_count,
    (SELECT COUNT(DISTINCT t.species_name) FROM tree_record t WHERE t.location_id = l.id AND t.status = 'alive') AS species_count,
    l.status
FROM location l
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

COMMIT;
