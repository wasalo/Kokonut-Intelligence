-- Eagle View: Platform Overview
-- High-level KPIs across the entire Kokonut Intelligence platform

SELECT
  (SELECT COUNT(*) FROM location WHERE status = 'active') as total_locations,
  (SELECT COUNT(*) FROM farm WHERE status = 'active') as total_farms,
  (SELECT COUNT(*) FROM plot) as total_plots,
  (SELECT COUNT(*) FROM crop_cycle WHERE status = 'active') as active_crop_cycles,
  (SELECT COUNT(*) FROM partner) as total_partners,
  (SELECT COUNT(*) FROM staff) as total_staff,
  (SELECT COUNT(*) FROM infrastructure_asset) as total_infrastructure;
