-- ============================================================
-- 058_spatial_export.sql — Seeds: Adelphi zone geometries
-- ============================================================

-- Update farm_zone records with PostGIS polygon geometries
-- Coordinates approximated around Adelphi farm in Dominican Republic (18.521, -69.987)

-- Syntropic Beds (0.78 ha) — rectangular plot
UPDATE farm_zone SET geometry = ST_GeomFromEWKT('SRID=4326;POLYGON((-69.98720 18.52080, -69.98680 18.52080, -69.98680 18.52110, -69.98720 18.52110, -69.98720 18.52080))')
WHERE zone_key = 'adelphi-syntropic-beds';

-- Agroforestry Corridor (0.45 ha) — L-shaped corridor
UPDATE farm_zone SET geometry = ST_GeomFromEWKT('SRID=4326;POLYGON((-69.98730 18.52110, -69.98690 18.52110, -69.98690 18.52130, -69.98710 18.52130, -69.98710 18.52140, -69.98730 18.52140, -69.98730 18.52110))')
WHERE zone_key = 'adelphi-agroforestry-corridor';

-- Nursery and Biofactory (0.10 ha) — small rectangular plot
UPDATE farm_zone SET geometry = ST_GeomFromEWKT('SRID=4326;POLYGON((-69.98740 18.52070, -69.98720 18.52070, -69.98720 18.52080, -69.98740 18.52080, -69.98740 18.52070))')
WHERE zone_key = 'adelphi-nursery-biofactory';

-- Poultry Loop (0.05 ha) — small circular-ish plot (approximated as polygon)
UPDATE farm_zone SET geometry = ST_GeomFromEWKT('SRID=4326;POLYGON((-69.98745 18.52065, -69.98735 18.52063, -69.98728 18.52068, -69.98730 18.52075, -69.98742 18.52073, -69.98745 18.52065))')
WHERE zone_key = 'adelphi-poultry-loop';

-- Update tree_record points with realistic GPS coordinates in the Agroforestry Corridor
UPDATE tree_record SET
    latitude = 18.52115 + (random() * 0.00020),
    longitude = -69.98715 + (random() * 0.00020)
WHERE plot_id = 'a0000000-0000-0000-0000-000000000021'
  AND species_name = 'Cocos nucifera';

-- Update tree_record points for passion fruit in Syntropic Beds
UPDATE tree_record SET
    latitude = 18.52095 + (random() * 0.00010),
    longitude = -69.98695 + (random() * 0.00010)
WHERE plot_id = 'a0000000-0000-0000-0000-000000000020'
  AND species_name = 'Passiflora edulis';
