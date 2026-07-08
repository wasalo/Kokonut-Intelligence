-- ============================================================
-- 059_drone_raster_integration.sql — Seeds: Adelphi pilot data
-- ============================================================

-- Adelphi pilot: MSAVI values for existing remote sensing observations
UPDATE remote_sensing_observation SET msavi = 0.45
WHERE location_id = 'a0000000-0000-0000-0000-000000000001'
  AND source = 'drone';

-- Adelphi pilot: raster metadata (drone orthomosaic)
INSERT INTO raster_metadata (
    id, location_id, plot_id, raster_name, raster_type,
    file_url, file_format, resolution_m,
    bbox_west, bbox_south, bbox_east, bbox_north,
    capture_date, capture_method, sensor, processing_pipeline,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005910',
 'a0000000-0000-0000-0000-000000000001',
 NULL,
 'Adelphi Farm Orthomosaic 2026-06', 'orthomosaic',
 'https://storage.example.com/adelphi/ortho_2026_06.tif', 'geotiff', 0.05,
 -69.988, 18.520, -69.986, 18.522,
 '2026-06-15', 'fixed_wing_drone', 'DJI Phantom 4 RTK', 'Pix4Dmapper',
 'processed', 'pilot_seed', 'adelphi-ortho-2026-06',
 '{"record_type":"raster_metadata","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005911',
 'a0000000-0000-0000-0000-000000000001',
 NULL,
 'Adelphi NDVI Raster 2026-06', 'ndvi_raster',
 'https://storage.example.com/adelphi/ndvi_2026_06.tif', 'geotiff', 0.10,
 -69.988, 18.520, -69.986, 18.522,
 '2026-06-15', 'fixed_wing_drone', 'DJI Phantom 4 RTK', 'Pix4Dmapper + custom NDVI',
 'processed', 'pilot_seed', 'adelphi-ndvi-2026-06',
 '{"record_type":"raster_metadata","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();

-- Adelphi pilot: spatial clusters (DBSCAN results)
INSERT INTO spatial_cluster (
    id, location_id, cluster_method, cluster_name, cluster_type,
    tree_count, avg_health_score, dominant_species, avg_height_m,
    compactness, eps_m, min_samples,
    centroid_geometry, notes,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005920',
 'a0000000-0000-0000-0000-000000000001',
 'dbscan', 'Mature Coconut Group', 'species_group',
 8, 90.5, 'Cocos nucifera', 12.3,
 0.85, 50.0, 3,
 ST_SetSRID(ST_MakePoint(-69.98705, 18.52110), 4326),
 'Tight cluster of 8 mature coconut palms in the agroforestry corridor. High health scores, consistent height.',
 'pilot_seed', 'adelphi-cluster-mature-coconut',
 '{"record_type":"spatial_cluster","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005921',
 'a0000000-0000-0000-0000-000000000001',
 'dbscan', 'Juvenile Coconut Group', 'age_group',
 5, 71.0, 'Cocos nucifera', 6.8,
 0.78, 40.0, 3,
 ST_SetSRID(ST_MakePoint(-69.98712, 18.52125), 4326),
 'Younger coconut palms planted 2021-2022. Lower health scores, growing well.',
 'pilot_seed', 'adelphi-cluster-juvenile-coconut',
 '{"record_type":"spatial_cluster","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005922',
 'a0000000-0000-0000-0000-000000000001',
 'dbscan', 'Passion Fruit Bed', 'species_group',
 3, 83.7, 'Passiflora edulis', 3.0,
 0.92, 20.0, 2,
 ST_SetSRID(ST_MakePoint(-69.98695, 18.52095), 4326),
 'Passion fruit vines in the syntropic beds. Healthy, productive.',
 'pilot_seed', 'adelphi-cluster-passion-fruit',
 '{"record_type":"spatial_cluster","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    tree_count = EXCLUDED.tree_count,
    updated_at = NOW();

-- Adelphi pilot: pest hotspot (minor)
INSERT INTO pest_hotspot (
    id, location_id, hotspot_name, pest_or_disease,
    tree_count_affected, avg_severity, radius_m, area_m2,
    confidence_score, detection_date, detection_method,
    recommended_action, status,
    centroid_geometry, notes,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005930',
 'a0000000-0000-0000-0000-000000000001',
 'Minor Aphid Cluster - AC-004/AC-005', 'Aphid (Aphis gossypii)',
 2, 25.0, 15.0, 707.0,
 85.0, '2026-06-01', 'field_observation',
 'Monitor and apply neem oil if severity increases. Already biocontrol-ready.',
 'monitoring',
 ST_SetSRID(ST_MakePoint(-69.987035, 18.521070), 4326),
 'Two adjacent coconut palms (AC-004, AC-005) showing minor aphid presence. Low severity. Natural enemies observed nearby.',
 'pilot_seed', 'adelphi-pest-aphid-minor',
 '{"record_type":"pest_hotspot","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();
