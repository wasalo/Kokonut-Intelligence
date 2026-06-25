-- ============================================================
-- Seed: Carbon framework reference data
-- ============================================================
-- Emission factors (IPCC 2006 / Caribbean / East Africa defaults),
-- carbon benchmarks for tree systems, and operations protocols.

-- GHG Emission factors
INSERT INTO ghg_emission_factor (factor_key, category, subcategory, emission_factor, unit, source, region, valid_from, metadata) VALUES
-- Fuels (IPCC 2006, Volume 2, Table 2.2)
('diesel_dominican_republic', 'fuel', 'diesel', 2.68, 'litre', 'IPCC 2006 Vol 2 Table 2.2', 'dominican_republic', '2024-01-01', '{"source_url":"https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_2_Ch2_Complete.pdf"}'::jsonb),
('petrol_dominican_republic', 'fuel', 'petrol', 2.31, 'litre', 'IPCC 2006 Vol 2 Table 2.2', 'dominican_republic', '2024-01-01', '{}'::jsonb),
('lpg_dominican_republic', 'fuel', 'lpg', 1.51, 'litre', 'IPCC 2006 Vol 2 Table 2.2', 'dominican_republic', '2024-01-01', '{}'::jsonb),
('diesel_east_africa', 'fuel', 'diesel', 2.68, 'litre', 'IPCC 2006 Vol 2 Table 2.2', 'east_africa', '2024-01-01', '{}'::jsonb),
('petrol_east_africa', 'fuel', 'petrol', 2.31, 'litre', 'IPCC 2006 Vol 2 Table 2.2', 'east_africa', '2024-01-01', '{}'::jsonb),
('diesel_global', 'fuel', 'diesel', 2.68, 'litre', 'IPCC 2006 Vol 2 Table 2.2', 'global', '2024-01-01', '{}'::jsonb),
('petrol_global', 'fuel', 'petrol', 2.31, 'litre', 'IPCC 2006 Vol 2 Table 2.2', 'global', '2024-01-01', '{}'::jsonb),
-- Fertilizers (IPCC 2006, Volume 4, Table 4.2)
('npk_fertilizer', 'fertilizer', 'npk', 4.53, 'kg', 'IPCC 2006 Vol 4 Table 4.2', 'global', '2024-01-01', '{"note":"N2O emissions from synthetic N application"}'::jsonb),
('urea_fertilizer', 'fertilizer', 'urea', 5.23, 'kg', 'IPCC 2006 Vol 4 Table 4.2', 'global', '2024-01-01', '{"note":"N2O + CO2 from urea hydrolysis"}'::jsonb),
('compost_organic', 'fertilizer', 'compost', 0.05, 'kg', 'IPCC 2006 Vol 4 Table 4.2', 'global', '2024-01-01', '{"note":"Low emission factor for well-managed compost"}'::jsonb),
('biofertilizer', 'fertilizer', 'biofertilizer', 0.02, 'kg', 'estimate', 'global', '2024-01-01', '{"note":"On-farm biofactory production, minimal emissions"}'::jsonb),
-- Pesticides (IPCC 2006, Volume 4)
('pesticide_synthetic', 'pesticide', 'synthetic', 5.1, 'kg', 'IPCC 2006 Vol 4', 'global', '2024-01-01', '{}'::jsonb),
('pesticide_organic', 'pesticide', 'organic', 0.3, 'kg', 'estimate', 'global', '2024-01-01', '{"note":"Neem, biopesticides, minimal emissions"}'::jsonb),
-- Transport (fuel-based, derived from fuel factors)
('truck_transport_diesel', 'transport', 'truck', 2.68, 'km', 'IPCC 2006 + fleet average', 'global', '2024-01-01', '{"note":"Approx 1 litre diesel per km for small truck"}'::jsonb),
('motorcycle_transport', 'transport', 'motorcycle', 0.15, 'km', 'IPCC 2006 + fleet average', 'global', '2024-01-01', '{"note":"Approx 0.065 litre per km motorcycle"}'::jsonb),
-- Machinery
('tractor_diesel', 'machinery', 'tractor', 2.68, 'hour', 'IPCC 2006 + equipment average', 'global', '2024-01-01', '{"note":"Approx 1 litre diesel per hour small tractor"}'::jsonb),
('chainsaw', 'machinery', 'chainsaw', 0.75, 'hour', 'IPCC 2006 + equipment average', 'global', '2024-01-01', '{"note":"Petrol chainsaw ~0.33 L/hr"}'::jsonb),
-- Electricity
('electricity_global', 'electricity', 'grid', 0.50, 'kwh', 'IEA 2023 global average', 'global', '2024-01-01', '{}'::jsonb),
('electricity_dominican_republic', 'electricity', 'grid', 0.54, 'kwh', 'ONE Dominicana 2023', 'dominican_republic', '2024-01-01', '{}'::jsonb)
ON CONFLICT (factor_key) DO UPDATE SET
    category = EXCLUDED.category,
    subcategory = EXCLUDED.subcategory,
    emission_factor = EXCLUDED.emission_factor,
    unit = EXCLUDED.unit,
    source = EXCLUDED.source,
    region = EXCLUDED.region,
    valid_from = EXCLUDED.valid_from,
    metadata = EXCLUDED.metadata;

-- Carbon benchmarks for tree systems (literature-based)
INSERT INTO carbon_benchmark (benchmark_key, name, tree_system, above_ground_carbon_tonnes_ha, below_ground_carbon_tonnes_ha, total_carbon_tonnes_ha, sequestration_rate_tonnes_co2e_ha_year, source, region, notes) VALUES
('coconut_mature', 'Mature Coconut (20+ years)', 'coconut', 45.0, 12.0, 57.0, 8.5, 'Nair et al. 2009; IPCC 2006 Vol 4', 'tropical', 'Mature coconut palm ~300 kg C/tree at 150 trees/ha; below-ground ~25% of above-ground'),
('coconut_young', 'Young Coconut (5-10 years)', 'coconut', 8.0, 2.5, 10.5, 5.0, 'Rajagopalan et al. 2018', 'tropical', 'Young palm accumulating biomass rapidly'),
('coconut_agroforestry', 'Coconut Agroforestry System', 'coconut', 55.0, 15.0, 70.0, 12.0, 'Nair et al. 2009; Koh et al. 2021', 'tropical', 'Coconut + multi-strata companions; higher total carbon than monoculture'),
('oil_palm_plantation', 'Oil Palm Plantation', 'oil_palm', 40.0, 10.0, 50.0, 15.0, 'IPCC 2006 Vol 4; Corley 2009', 'tropical', 'High annual sequestration but shorter lifespan than coconut'),
('mature_mango', 'Mature Mango Orchard', 'mango', 65.0, 18.0, 83.0, 4.0, 'Kumar & Nair 2004', 'tropical', 'High biomass accumulation, moderate sequestration rate'),
('mature_cacao', 'Cacao Under Shade', 'cacao', 25.0, 8.0, 33.0, 6.0, 'Somarriba et al. 2013', 'tropical', 'Shade-grown cacao with companion canopy trees'),
('mixed_agroforestry_tropical', 'Mixed Tropical Agroforestry', 'mixed_agroforestry', 80.0, 22.0, 102.0, 10.0, 'Nair et al. 2009; Zomer et al. 2016', 'tropical', 'Diverse multi-strata systems with high total carbon'),
('native_forest_baseline', 'Native Tropical Forest (baseline)', 'native_forest', 120.0, 35.0, 155.0, 2.0, 'Pan et al. 2011', 'tropical', 'Reference point for natural carbon stock in tropical forest')
ON CONFLICT (benchmark_key) DO UPDATE SET
    name = EXCLUDED.name,
    tree_system = EXCLUDED.tree_system,
    above_ground_carbon_tonnes_ha = EXCLUDED.above_ground_carbon_tonnes_ha,
    below_ground_carbon_tonnes_ha = EXCLUDED.below_ground_carbon_tonnes_ha,
    total_carbon_tonnes_ha = EXCLUDED.total_carbon_tonnes_ha,
    sequestration_rate_tonnes_co2e_ha_year = EXCLUDED.sequestration_rate_tonnes_co2e_ha_year,
    source = EXCLUDED.source,
    region = EXCLUDED.region,
    notes = EXCLUDED.notes;

-- Operations protocols (versioned handbook sections)
INSERT INTO operations_protocol (protocol_key, title, section, content, version, effective_date, review_cadence, framework_key, status, metadata) VALUES
('soil_management_v1', 'Soil Management and Carbon Tracking', 'soil_management', '## Soil Management Protocol
### Purpose
Ensure consistent soil protection, carbon tracking, and data quality for grant compliance.

### Sampling Protocol
1. Sample each plot at planting and harvest (minimum 2x per crop cycle)
2. Use 0-30cm depth for topsoil carbon (standard IPCC depth)
3. Collect 5 composite samples per plot (zigzag pattern)
4. Label with plot_id, date, depth, and sample_id from lab
5. Store in sealed bags at 4C until delivery to lab

### Measurement Methods
- **Lab analysis** (preferred): Send to certified lab for SOC%, bulk density, NPK
- **Field estimate**: Use handheld soil meter for pH and moisture (validation only)

### Data Entry
- Record each measurement in `soil_carbon_measurement` within 48 hours
- Set `is_baseline=TRUE` for the first measurement per plot
- Link subsequent measurements via `baseline_id` to the baseline record

### Carbon Calculation
- Carbon stock (t/ha) = SOC% × bulk density × depth × 10
- Delta = latest carbon stock - baseline carbon stock
- CO2e = delta × 3.67 (carbon to CO2 conversion)

### Evidence Requirements
- Lab reports stored as evidence_urls
- Photos of sampling locations
- GPS coordinates of sample points (if available)', 'v1.0', '2025-01-01', 'annual', 'kokonut_framework', 'active', '{"source":"kokonut knowledge base","grant_relevance":"carbon evidence"}'::jsonb),
('biodiversity_v1', 'Biodiversity Monitoring Protocol', 'biodiversity', '## Biodiversity Monitoring Protocol
### Purpose
Track species diversity and support ecological evidence for EBF and SDG 15 reporting.

### Observation Schedule
- **Weekly**: Quick visual survey of plot perimeter (10 minutes)
- **Monthly**: Full species count with Shannon diversity index
- **Quarterly**: Camera trap or transect for fauna

### Data Entry
- Record each observation in `species_observation` table
- Include species_name, count, method, and habitat_type
- Attach photos as evidence_urls

### Shannon Diversity Index
- H = -sum(p_i * ln(p_i)) where p_i = proportion of species i
- Higher H = more diverse ecosystem
- Track delta over time to show improvement

### Indicator Species to Track
- Birds (pollination, pest control)
- Insects (pollination, decomposition)
- Soil organisms (health indicator)
- Companion planting survival rates

### Evidence Requirements
- Photos of species with date stamps
- Observer identification
- Method description in notes', 'v1.0', '2025-01-01', 'quarterly', 'kokonut_framework', 'active', '{"source":"kokonut knowledge base","grant_relevance":"biodiversity evidence"}'::jsonb),
('emissions_tracking_v1', 'GHG Emissions Tracking Protocol', 'emissions_tracking', '## GHG Emissions Tracking Protocol
### Purpose
Establish a greenhouse gas inventory covering transport, machinery, and inputs as required by grant reviewers.

### Scope
- **Transport**: Fuel consumption for farm-to-market, deliveries, commutes
- **Machinery**: Tractor hours, chainsaw usage, processing equipment
- **Inputs**: Synthetic fertilizer, pesticide, and purchased feed emissions

### Weekly Tracking (Field Workers)
1. Record fuel purchases with date, quantity, and type
2. Record machinery usage hours and fuel consumption
3. Record input applications (synthetic vs organic)

### Monthly Reporting (Farm Manager)
1. Enter all fuel and machinery data into `ghg_emissions_inventory`
2. Match each record to the correct `ghg_emission_factor`
3. Compute CO2e = quantity * emission_factor
4. Review for completeness

### Quarterly Review (Impact Lead)
1. Run `python3 -m services.analytics.cli --ghg-emissions --location-id UUID`
2. Compare to previous quarter
3. Identify reduction opportunities
4. Update mitigation actions

### Emission Factors
- Use `ghg_emission_factor` table for all calculations
- Default to IPCC 2006 factors for Dominican Republic / East Africa
- Update factors annually or when local data available

### Evidence Requirements
- Fuel receipts with dates
- Machinery logbook entries
- Input purchase invoices', 'v1.0', '2025-01-01', 'monthly', 'kokonut_framework', 'active', '{"source":"kokonut knowledge base","grant_relevance":"GHG baseline"}'::jsonb),
('data_entry_v1', 'Data Entry and Quality Protocol', 'data_entry', '## Data Entry and Quality Protocol
### Purpose
Ensure consistent, timely, and verifiable data entry across all farm locations.

### Cadence
| Activity | Frequency | Responsible | Deadline |
|----------|-----------|-------------|----------|
| Field observations | Weekly | Field worker | Within 48 hours |
| Soil measurements | Per crop cycle | Field supervisor | Within 1 week of lab results |
| Harvest records | Per harvest | Harvest lead | Within 24 hours |
| Financial records | Monthly | Farm manager | By 5th of month |
| GHG emissions | Monthly | Farm manager | By 10th of month |
| Framework assessment | Quarterly | Impact lead | By 15th of quarter |
| Annual summary | Annual | Impact lead | By January 31 |

### Quality Rules
1. Every record must have a date, location_id, and source_system
2. Use `status=draft` for initial entry, `status=submitted` for review
3. Attach evidence (photos, receipts, lab reports) as evidence_urls
4. Never leave amounts at NULL - use 0 if truly zero
5. Use consistent units (kg, tonnes, USD, metres)

### Verification Workflow
- Field worker creates (status=draft)
- Farm manager reviews (status=submitted)
- Impact lead verifies (status=verified)
- Published to dashboards and reports (status=published)', 'v1.0', '2025-01-01', 'monthly', 'kokonut_framework', 'active', '{"source":"kokonut knowledge base","grant_relevance":"operational evidence"}'::jsonb),
('reporting_v1', 'Annual Reporting Protocol', 'reporting', '## Annual Reporting Protocol
### Purpose
Produce a structured annual climate-impact report for grant reviewers, funders, and internal review.

### Timeline
| Month | Action | Owner |
|-------|--------|-------|
| January | Collect all data from previous year | Farm manager |
| February | Run carbon balance, GHG emissions, biodiversity analysis | Impact lead |
| March | Draft climate impact summary | Impact lead |
| March | Peer review by Impact Guild | Guild members |
| April | Publish and submit to grant reviewers | Communications |
| April | Retrospective meeting | All stakeholders |

### Report Components
1. **Carbon balance**: Sequestration vs emissions (v_carbon_balance)
2. **GHG inventory**: Breakdown by category (v_ghg_emissions_summary)
3. **Biodiversity outcomes**: Species count, Shannon index, key observations
4. **Regenerative practice score**: 5-principle assessment (v_regenerative_score_summary)
5. **Framework phase status**: Current implementation phase (v_framework_phase_status)
6. **Methodology notes**: Changes to methods, data quality assessment
7. **Next year targets**: Goals for next reporting period

### Data Sources
- Use `climate_impact_summary` table for the annual record
- Reference forecast outputs for projections
- Include confidence levels for all claims

### Review Cadence
- Annual retrospective in April
- Quarterly progress check-ins (Jan, Apr, Jul, Oct)
- Monthly data quality review', 'v1.0', '2025-01-01', 'annual', 'kokonut_framework', 'active', '{"source":"kokonut knowledge base","grant_relevance":"annual reporting"}'::jsonb)
ON CONFLICT (protocol_key) DO UPDATE SET
    title = EXCLUDED.title,
    section = EXCLUDED.section,
    content = EXCLUDED.content,
    version = EXCLUDED.version,
    effective_date = EXCLUDED.effective_date,
    review_cadence = EXCLUDED.review_cadence,
    framework_key = EXCLUDED.framework_key,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
