-- Pilot data stream posts for Kokonut Adelphi
-- 15 posts covering various types and statuses

INSERT INTO data_stream_post (
    id, location_id, post_type, title, content, visibility, status,
    evidence_urls, file_ids, media_type, is_anchored, chain,
    source_system, schema_version, created_at
) VALUES
-- Field updates (3)
('b0000000-0000-0000-0000-000000000101', 'a0000000-0000-0000-0000-000000000001',
 'field_update', 'Soil preparation complete for Zone A',
 'Completed deep tillage and compost application across 0.5 hectares in Zone A. Soil moisture levels are optimal for planting. Added 2 tons of organic compost mix.',
 'public', 'published',
 ARRAY['https://storage.example.com/field-updates/zone-a-soil-2026-07-01.jpg'],
 NULL, 'document', FALSE, 'celo',
 'manual', 'data-stream-v1', '2026-07-01 08:00:00+00'),

('b0000000-0000-0000-0000-000000000102', 'a0000000-0000-0000-0000-000000000001',
 'field_update', 'Irrigation system maintenance',
 'Serviced drip irrigation lines in Zone B. Replaced 3 clogged emitters. Flow rate restored to 2.1 L/hr per emitter. System pressure normalized at 1.2 bar.',
 'public', 'published',
 ARRAY['https://storage.example.com/field-updates/irrigation-maintenance.jpg'],
 NULL, 'document', FALSE, 'celo',
 'manual', 'data-stream-v1', '2026-07-03 14:30:00+00'),

('b0000000-0000-0000-0000-000000000103', 'a0000000-0000-0000-0000-000000000001',
 'field_update', 'Weekly team coordination meeting',
 'Held weekly coordination meeting with 8 field workers. Discussed planting schedule for next week, pest monitoring results, and water conservation strategies. Action items assigned.',
 'internal', 'submitted',
 NULL, NULL, NULL, FALSE, NULL,
 'manual', 'data-stream-v1', '2026-07-05 09:00:00+00'),

-- Photos (3)
('b0000000-0000-0000-0000-000000000104', 'a0000000-0000-0000-0000-000000000001',
 'photo', 'Zone A coconut seedlings - Day 14',
 'Photographic documentation of coconut seedlings at 14 days post-planting. Germination rate: 92%. Average height: 15cm. No signs of disease or pest damage.',
 'public', 'published',
 ARRAY['https://storage.example.com/photos/zone-a-seedlings-day14-1.jpg',
        'https://storage.example.com/photos/zone-a-seedlings-day14-2.jpg'],
 NULL, 'image', FALSE, 'celo',
 'manual', 'data-stream-v1', '2026-07-02 10:15:00+00'),

('b0000000-0000-0000-0000-000000000105', 'a0000000-0000-0000-0000-000000000001',
 'photo', 'Biodiversity corridor - native species survey',
 'Photo documentation of biodiversity corridor between Zone A and Zone B. Observed 12 native plant species, 3 butterfly species, and 2 bird species during 30-minute survey.',
 'public', 'published',
 ARRAY['https://storage.example.com/photos/biodiversity-corridor-jul-2026.jpg'],
 NULL, 'image', FALSE, 'celo',
 'manual', 'data-stream-v1', '2026-07-04 16:00:00+00'),

('b0000000-0000-0000-0000-000000000106', 'a0000000-0000-0000-0000-000000000001',
 'photo', 'Compost production area setup',
 'New compost production area established with 3-bin system. Carbon:nitrogen ratio optimized at 30:1. Temperature monitoring probes installed.',
 'internal', 'verified',
 ARRAY['https://storage.example.com/photos/compost-area-setup.jpg'],
 NULL, 'image', FALSE, NULL,
 'manual', 'data-stream-v1', '2026-07-06 11:00:00+00'),

-- Monitoring reports (3)
('b0000000-0000-0000-0000-000000000107', 'a0000000-0000-0000-0000-000000000001',
 'monitoring_report', 'Monthly soil moisture monitoring - June 2026',
 'Comprehensive soil moisture monitoring report for June 2026. Average volumetric water content: Zone A 28%, Zone B 31%, Zone C 25%. All zones within optimal range (20-35%). No irrigation stress detected.',
 'public', 'published',
 ARRAY['https://storage.example.com/reports/soil-moisture-june-2026.pdf'],
 NULL, 'document', TRUE, 'celo',
 'sensor_network', 'data-stream-v1', '2026-07-01 07:00:00+00'),

('b0000000-0000-0000-0000-000000000108', 'a0000000-0000-0000-0000-000000000001',
 'monitoring_report', 'Pest monitoring report - Week 27',
 'Weekly pest monitoring completed. Low aphid activity detected in Zone B (2 plants affected). Natural predator population (ladybugs) sufficient for biological control. No chemical intervention required.',
 'public', 'published',
 ARRAY['https://storage.example.com/reports/pest-week27.pdf'],
 NULL, 'document', FALSE, 'celo',
 'manual', 'data-stream-v1', '2026-07-07 08:30:00+00'),

('b0000000-0000-0000-0000-000000000109', 'a0000000-0000-0000-0000-000000000001',
 'monitoring_report', 'Water quality test results',
 'Quarterly water quality analysis from irrigation source. pH: 6.8 (optimal), EC: 0.45 dS/m (low salinity), nitrate: 12 mg/L (adequate), phosphate: 3 mg/L. All parameters within organic certification limits.',
 'public', 'published',
 ARRAY['https://storage.example.com/reports/water-quality-q2-2026.pdf'],
 NULL, 'document', TRUE, 'celo',
 'lab_analysis', 'data-stream-v1', '2026-07-08 12:00:00+00'),

-- Sensor readings (3)
('b0000000-0000-0000-0000-000000000110', 'a0000000-0000-0000-0000-000000000001',
 'sensor_reading', 'Automated weather station daily summary',
 'Daily weather summary from on-farm station. Max temp: 32.4C, Min temp: 22.1C, Rainfall: 0mm, Humidity: 78%, Wind: 8 km/h NE. Evapotranspiration: 4.2mm.',
 'public', 'published',
 NULL, NULL, 'sensor_data', TRUE, 'celo',
 'openweathermap', 'data-stream-v1', '2026-07-09 06:00:00+00'),

('b0000000-0000-0000-0000-000000000111', 'a0000000-0000-0000-0000-000000000001',
 'sensor_reading', 'Soil temperature sensor - Zone A',
 'Soil temperature reading at 30cm depth. Temperature: 24.8C (optimal for coconut root development). Sensor ID: temp-z30-a01. Battery: 87%.',
 'internal', 'published',
 NULL, NULL, 'sensor_data', FALSE, NULL,
 'iot_sensor', 'data-stream-v1', '2026-07-09 14:00:00+00'),

('b0000000-0000-0000-0000-000000000112', 'a0000000-0000-0000-0000-000000000001',
 'sensor_reading', 'NDVI satellite imagery analysis',
 'Sentinel-2 NDVI analysis for July 2026. Average NDVI: 0.72 (healthy vegetation). Zone A: 0.78, Zone B: 0.71, Zone C: 0.67. Improvement of +0.05 compared to June.',
 'public', 'published',
 ARRAY['https://storage.example.com/satellite/ndvi-july-2026.tif'],
 NULL, 'satellite', TRUE, 'celo',
 'remote_sensing', 'data-stream-v1', '2026-07-10 08:00:00+00'),

-- Community updates (3)
('b0000000-0000-0000-0000-000000000113', 'a0000000-0000-0000-0000-000000000001',
 'community_update', 'Training session: Organic composting techniques',
 'Conducted 4-hour training session for 12 community members on organic composting techniques. Topics covered: carbon:nitrogen ratios, temperature monitoring, turning schedule, and quality indicators. Participants received practical hands-on experience.',
 'public', 'published',
 ARRAY['https://storage.example.com/training/composting-jul-2026.pdf'],
 NULL, 'document', FALSE, 'celo',
 'manual', 'data-stream-v1', '2026-07-05 14:00:00+00'),

('b0000000-0000-0000-0000-000000000114', 'a0000000-0000-0000-0000-000000000001',
 'community_update', 'Women cooperative meeting - July',
 'Monthly meeting of the women cooperative. 15 members attended. Discussed market access strategies, value-added product development, and savings group performance. Cooperative savings: $2,400 USD.',
 'public', 'published',
 NULL, NULL, NULL, FALSE, NULL,
 'manual', 'data-stream-v1', '2026-07-06 10:00:00+00'),

('b0000000-0000-0000-0000-000000000115', 'a0000000-0000-0000-0000-000000000001',
 'community_update', 'Youth environmental education program',
 'Launched environmental education program with local school. 25 students participated in tree planting activity, planting 50 native species along the biodiversity corridor. Students learned about ecosystem services and regenerative agriculture.',
 'public', 'published',
 ARRAY['https://storage.example.com/community/youth-education-jul-2026.jpg'],
 NULL, 'image', FALSE, 'celo',
 'manual', 'data-stream-v1', '2026-07-08 09:00:00+00')
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    content = EXCLUDED.content,
    visibility = EXCLUDED.visibility,
    status = EXCLUDED.status,
    evidence_urls = EXCLUDED.evidence_urls,
    media_type = EXCLUDED.media_type,
    is_anchored = EXCLUDED.is_anchored,
    chain = EXCLUDED.chain;

-- Seed comments on a few posts
INSERT INTO data_stream_post_comment (id, post_id, content, status, created_at) VALUES
('c0000000-0000-0000-0000-000000000101', 'b0000000-0000-0000-0000-000000000104',
 'Excellent germination rate! The seedling nursery setup is working well.', 'published', '2026-07-03 09:00:00+00'),
('c0000000-0000-0000-0000-000000000102', 'b0000000-0000-0000-0000-000000000107',
 'Data looks good. Soil moisture levels are well-managed.', 'published', '2026-07-02 11:00:00+00'),
('c0000000-0000-0000-0000-000000000103', 'b0000000-0000-0000-0000-000000000113',
 'Great training session! Participants were very engaged. Looking forward to the follow-up.', 'published', '2026-07-06 08:00:00+00')
ON CONFLICT (id) DO UPDATE SET
    content = EXCLUDED.content,
    status = EXCLUDED.status;
