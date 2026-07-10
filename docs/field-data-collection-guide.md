# Field Data Collection Guide

Detailed standard operating procedures (SOPs) for on-ground data collection across all measurement domains. This guide is designed as a generic template that any farm can adapt to its local context.

## 1. Overview & Principles

### 1.1 Evidence Maturity

All field data enters the governed lifecycle at Level 1 (self-reported). Data matures through verification:

| Level | Requirement | Typical Field Entry |
|-------|-------------|-------------------|
| 1 | Field entry submitted | GPS-tagged observation, photos |
| 2 | Structured data with GPS + photos | Lab results attached |
| 3 | Reviewed by supervisor | Cross-checked against expectations |
| 4 | Evidence-linked with lab reports | Public claim allowed |
| 5 | Attested on-chain via EAS | Carbon claims (non-public) |
| 6 | Externally verified with methodology | Public carbon claims |

### 1.2 Privacy Principles

- Field worker identities are private by default
- GPS coordinates of sensitive locations (nurseries, water sources) may be restricted
- Community observations are private unless `consent_given = TRUE`
- Lab reports are linked but stored off-chain (CID/URL only)

### 1.3 Data Quality Principles

- **Accuracy**: Measure to the precision your instruments allow
- **Completeness**: Fill all required fields — missing data is worse than estimated data
- **Timeliness**: Enter data within 24 hours of collection
- **Consistency**: Use the same methods, units, and naming conventions every time
- **Traceability**: Every data point must have a who/when/where/evidence trail

---

## 2. Equipment Catalog

### 2.1 Soil Tools

| Equipment | Specification | Purpose | Notes |
|-----------|--------------|---------|-------|
| Soil auger | Stainless steel, 0-30cm depth, 2.5cm diameter | Core sample collection | Avoid brass/copper (contaminates metal analysis) |
| Hand trowel | Stainless steel, 15cm blade | Surface sample collection | For litter/humus layer only |
| pH meter | Portable, resolution 0.01, calibration solutions pH 4.0/7.0/10.0 | Field pH measurement | Calibrate weekly; store electrode in KCl solution |
| Soil moisture meter | TDR or FDR type, 0-100% volumetric | Quick moisture check | Not a substitute for gravimetric lab analysis |
| Sample bags | Ziplock, 500ml minimum, labeled | Sample containment | Use separate bags for NPK vs carbon analysis |
| Clean bucket | Plastic or stainless steel, 5L | Sub-sample mixing | Wash between locations with distilled water |
| Soil knife / spatula | Stainless steel | Sample trimming and mixing | |
| GPS device | Handheld or smartphone, ±3m accuracy | Location tagging | Record at sub-sample level |
| Field notebook | Weather-resistant paper | Manual recording | Backup for digital entry |
| Data sheet | Printed form with plot ID, date, fields | Structured recording | Laminate for reuse |

### 2.2 Tree Measurement Tools

| Equipment | Specification | Purpose | Notes |
|-----------|--------------|---------|-------|
| DBH tape | fiberglass or steel, mm markings, 0.1cm resolution | Diameter at breast height | Wrap snugly but not tight enough to compress bark |
| Clinometer | Suunto or equivalent, ±0.5° accuracy | Tree height estimation | Stand 10-15m from tree; practice before field work |
| Laser hypsometer | Nikon Forestry Pro or similar | Tree height (direct) | More accurate than clinometer; requires line of sight to top |
| Diameter tape | For stems <5cm DBH | Sapling diameter | Alternative to calipers for small stems |
| Tree tags | Aluminum, numbered, 50x25mm, nail attachment | Individual tree identification | Never reuse numbers; use permanent markers |
| Measuring tape | 50m fiberglass, mm markings | Canopy diameter | Measure longest axis + perpendicular axis |
| Tree marker paint | Fluorescent, slow-dry | Mark trees for re-measurement | Use sparingly — environmental impact |
| GPS device | Handheld or smartphone, ±3m | Tree location | Record latitude/longitude for each tree |
| Clinometer app | Smartphone app (e.g., Forest Tools, Theodolite) | Backup height estimation | Less accurate than physical clinometer; acceptable for monitoring |

### 2.3 Biodiversity Survey Tools

| Equipment | Specification | Purpose | Notes |
|-----------|--------------|---------|-------|
| Quadrat frame | 1m x 1m or 2m x 2m, PVC or aluminum | Ground cover sampling | Weighted with sandbags in windy conditions |
| Transect tape | 50m or 100m, fiberglass, meter markings | Line transect surveys | Mark start/end with stakes |
| Binoculars | 8x42 or 10x42, waterproof | Bird/mammal observation | |
| Camera trap | Trail camera, IR flash, 12+ month battery | Nocturnal/secretive species | Mount 30-50cm above ground; face north |
| Hand lens | 10x-20x magnification | Insect/plant identification | |
| Specimen jars | Clear plastic, 100ml, with ethanol 70% | Insect voucher collection | Label with date, location, collector |
| Pheromone traps | Species-specific lures | Targeted insect monitoring | Replace lures per manufacturer schedule |
| Yellow sticky traps | 10x15cm, yellow, non-toxic adhesive | Flying insect monitoring | Check weekly; replace weekly |
| Pitfall traps | Plastic cups (500ml), flush with ground | Ground-dwelling insects | Cover with rain shield; check daily |
| Identification guides | Regional field guides, iNaturalist app, Merlin (birds) | Species identification | Photograph unknown species for later ID |
| GPS device | Handheld or smartphone | Survey point/location tagging | |
| Binoculars harness | Chest harness | Comfortable carrying | Reduces fatigue during long surveys |

### 2.4 Water Sampling Tools

| Equipment | Specification | Purpose | Notes |
|-----------|--------------|---------|-------|
| Sample bottles | 500ml plastic (nutrients) or glass (metals/organics) | Sample containment | Rinse 3x with sample water before collection |
| Depth sampler | Weighted bottle on rope, 0-5m depth | Groundwater/deep surface sampling | Lower slowly; close at desired depth |
| Portable pH/EC meter | Dual-parameter, calibration solutions | Field screening | Calibrate before each sampling event |
| Thermometer | Digital, ±0.1°C, waterproof | Water temperature | Read before sample preservation |
| Dissolved oxygen meter | Portable, galvanic or optical | DO field measurement | Calibrate in air-saturated water |
| Turbidity tube | 0-100 NTU range | Visual turbidity estimation | Simple field method; compare to NTU standards |
| Ice box / cooler | Insulated, with ice packs | Sample preservation (4°C) | Pre-cool before sample collection |
| Chain of custody labels | Waterproof, adhesive, unique ID | Sample tracking | Write with permanent marker; affix to bottle |
| Sample preservatives | H2SO4 (nutrients), Na2S2O3 (chlorine), ice | Sample preservation | Follow lab requirements; use PPE |
| GPS device | Handheld or smartphone | Sampling point location | Record at collection point |

### 2.5 Weather Tools (On-Site)

| Equipment | Specification | Purpose | Notes |
|-----------|--------------|---------|-------|
| Rain gauge | Standard 203mm diameter, 0.2mm resolution | Precipitation measurement | Mount 30cm above ground, level, unobstructed |
| Max/min thermometer | Digital, -40°C to +60°C range | Temperature extremes | Reset daily; read at same time each day |
| Hygrometer | Digital, 0-100% RH | Relative humidity | Place in ventilated radiation shield |
| Anemometer | Cup or propeller type, 0-60 m/s | Wind speed | Mount 2m above ground in open area |
| Wind vane | Standard, north-aligned | Wind direction | |
| Data logger | 12V, solar-compatible, multi-channel | Continuous recording | For permanent weather stations |

### 2.6 Harvest Tools

| Equipment | Specification | Purpose | Notes |
|-----------|--------------|---------|-------|
| Platform scale | 50kg capacity, 10g resolution, certified | Fresh weight measurement | Calibrate monthly with certified weights |
| Hanging scale | 10kg capacity, 5g resolution | Small quantity weighing | |
| Moisture meter | Crop-specific calibration (maize, rice, beans) | Moisture content | Check calibration against oven-dried sample quarterly |
| Digital calipers | 0-150mm, 0.01mm resolution | Fruit/produce size | |
| Quality grading board | Laminated photo reference | Consistent quality grading | Grade A/B/C reference images specific to crop |
| Sample bags | Paper (for moisture samples) or ziplock (for general) | Sub-sampling | Paper bags for moisture — no plastic (traps moisture) |
| Container tare card | Labeled card with container weight | Tare recording | Update after cleaning |

### 2.7 Pest Monitoring Tools

| Equipment | Specification | Purpose | Notes |
|-----------|--------------|---------|-------|
| Yellow sticky traps | 10x15cm, non-toxic | Flying insect monitoring | Place at canopy height; check/replace weekly |
| Blue sticky traps | 10x15cm, non-toxic | Thrips-specific monitoring | |
| Pheromone traps | Species-specific lure + delta trap | Targeted pest monitoring | Replace lures per manufacturer schedule |
| Hand lens | 10x-20x magnification | Pest identification | |
| Spade / soil corer | Stainless steel, 10cm diameter | Soil-dwelling pest sampling | Core to 20cm depth; sift through soil |
| Sample vials | Clear plastic, 50ml | Specimen collection | Label with date, location, host plant |
| Camera | Smartphone or macro lens | Damage/pest documentation | Photograph both pest and damage |

---

## 3. Soil Sampling Protocol

### 3.1 Sampling Design

- Use `sample_plot_design` for plot-based sampling (simple random, stratified random, or systematic grid)
- **5 sub-samples per composite sample** (stratified across the plot)
- GPS-tag each sub-sample location (record latitude/longitude)
- Avoid: field edges, anthills, tree bases, fertilizer/liming spots, animal paths, irrigation furrows
- Minimum 5 composite samples per management zone for statistical validity

### 3.2 Collection Procedure

1. **Clear surface litter** from a 30cm diameter circle before augering
2. **Insert auger vertically** to target depth:
   - Topsoil: 0-15cm (most common for fertility testing)
   - Full root zone: 0-30cm (for carbon and deeper nutrient profiles)
   - Subsoil: 30-60cm (for diagnostic purposes only)
3. **Extract core** carefully — avoid crumbling or losing material
4. **Place in clean bucket** — repeat for 5 sub-samples across the plot
5. **Mix thoroughly** in the bucket — remove stones, roots, large organic debris
6. **Transfer 500g** (minimum) to a labeled sample bag
7. **Record on data sheet**: plot ID, date, time, depth, GPS, moisture conditions (wet/moist/dry), observer name
8. **Air-dry samples** if lab requires (spread on clean paper in shade for 48-72 hours)

### 3.3 Lab Submission

1. Complete **chain of custody form** with: sample ID, collector, date, GPS, requested analyses
2. Submit within **48 hours** of collection (or per lab requirements)
3. Request **standard soil panel**: pH, organic matter %, nitrogen (N), phosphorus (P), potassium (K), CEC, texture
4. For carbon analysis: request **dry combustion** (preferred) or **Walkley-Black** method
5. Retain a **duplicate sample** in the fridge (4°C) for re-analysis if needed

### 3.4 Frequency

| Phase | Frequency | Notes |
|-------|-----------|-------|
| Baseline | Once at project start | Establish reference values |
| Monitoring | Quarterly or semi-annually | Seasonal variation affects readings |
| Event-triggered | After major input application or land use change | Captures management impact |

### 3.5 Data Entry

1. Create `soil_sample` record with lab results when received
2. If carbon analysis requested: also create `soil_carbon_measurement` record
3. Set `is_baseline = TRUE` for initial sampling
4. Set `evidence_maturity` based on lab report availability:
   - Level 1: field entry only
   - Level 2: with GPS + photos
   - Level 4: with lab report attached
5. Store lab report URL in `lab_report_url` field
6. Link to plot and location via `plot_id` and `location_id`

---

## 4. Tree Measurement Protocol

### 4.1 Plot Selection & Tagging

- Use `sample_plot_design` for permanent sample plots
- Mark **all trees** within each plot with numbered aluminum tree tags
- GPS-tag each tree location (latitude/longitude)
- Record plot boundary coordinates for spatial reference
- Tree tag naming convention: `{plot_number}-{species_code}-{sequential_number}` (e.g., `P01-COC-001` for coconut tree #1 in plot 1)

### 4.2 DBH Measurement (Diameter at Breast Height)

1. **Locate breast height**: 1.3m above ground level
2. **On flat ground**: measure directly around the stem at 1.3m
3. **On sloped ground**: measure on the **uphill side** of the tree at 1.3m from ground level
4. **Wrap tape snugly** around the stem — not tight enough to compress bark, not loose enough to gap
5. **Read to 0.1cm** (e.g., 25.4 cm)
6. **For buttressed trees**: measure at the top of the buttress (typically 1.5-2m)
7. **For multi-stem trees**: measure each stem separately; report the largest in the main record, note others in notes field
8. **For saplings (<5cm DBH)**: use diameter tape or digital calipers at 30cm above ground

### 4.3 Height Measurement

**Method 1: Clinometer (most common)**
1. Stand 10-15m from the tree (distance must be greater than tree height)
2. Sight the tree top — read angle from clinometer
3. Sight the tree base (at your feet) — read angle from clinometer
4. Height = distance × (tan(top_angle) + tan(base_angle))
5. Record in meters (e.g., 8.5 m)

**Method 2: Laser Hypsometer (most accurate)**
1. Stand at measured distance from tree
2. Sight tree top — press button to get height directly
3. Record the displayed height in meters

**Method 3: Smartphone Clinometer App (acceptable for monitoring)**
1. Open clinometer app, calibrate to your eye height
2. Sight tree top and base, read angles
3. Calculate height using the app or manual formula
4. Accuracy: ±1m (acceptable for monitoring, not for carbon accounting)

**For seedlings <1m**: measure directly with a measuring tape from ground to tip.

### 4.4 Canopy Diameter

1. Measure the **longest axis** of the canopy (N-S or E-W direction)
2. Measure the **perpendicular axis** (90° to the first measurement)
3. **Average** of the two axes = canopy diameter
4. Record in meters (e.g., 3.2 m)

### 4.5 Health Score (0-100)

| Score | Assessment |
|-------|-----------|
| 90-100 | Healthy: full canopy, vibrant color, no visible damage |
| 70-89 | Minor issues: some leaf loss (<20%), minor pest damage, slight discoloration |
| 50-69 | Moderate stress: significant leaf loss (20-50%), disease present, partial dieback |
| 30-49 | Severe stress: major dieback (>50%), extensive disease/pest damage, stunted growth |
| 0-29 | Dead or dying: no live canopy, structural collapse, no recovery signs |

Assessment factors: leaf color, canopy density, pest damage, disease signs, deadwood percentage, new growth presence.

### 4.6 Frequency

| Maturity Stage | Frequency | Override |
|---------------|-----------|---------|
| Seedling (<1 year) | Monthly | — |
| Juvenile (1-5 years) | Quarterly | — |
| Mature (>5 years) | Semi-annually or annually | — |
| Any stage | Per `measurement_frequency` field on `tree_record` | Zone default if NULL |

### 4.7 Data Entry

1. Create `tree_measurement` record for each measured tree
2. Update `tree_record` with latest measurement values
3. Create/update `tree_inventory` aggregate (species-level summary)
4. `tree_inventory` feeds carbon calculation via allometric model (height + DBH → biomass → carbon → CO2e)
5. Ensure `allometric_source` field references the equation used

---

## 5. Biodiversity Survey Protocol

### 5.1 Survey Methods

**Method 1: Quadrat Sampling (ground cover, herbs, small plants)**
- Place 1m² or 2m² frame randomly within plot
- Record all plant species within frame, their cover %, and height
- Minimum 5 quadrats per plot
- Best for: herbaceous layer, ground cover, seedling density

**Method 2: Line Transect (birds, mammals, large plants)**
- Lay 50-100m tape through plot
- Walk slowly, record all species seen/heard within 5m either side
- Record distance from start point for each observation
- Best for: birds, mammals, large plants, linear habitat features

**Method 3: Point Count (birds, acoustic monitoring)**
- Stand at fixed point, count all birds seen/heard within 5 minutes
- Record within 100m radius
- Minimum 3 points per plot, spaced >100m apart
- Best for: bird diversity, relative abundance

**Method 4: Camera Trap (nocturnal, secretive species)**
- Mount at 30-50cm above ground, facing a game trail or water source
- Set to trigger on motion, record 30-second video clips
- Deploy for 1-2 weeks minimum
- Best for: small mammals, reptiles, nocturnal species

**Method 5: Pitfall Traps (ground-dwelling insects)**
- Sink 500ml plastic cups flush with ground surface
- Arrange in a line of 5 cups, 5m apart
- Add preservative (ethylene glycol or soapy water)
- Check daily, collect specimens
- Best for: ground beetles, spiders, ants

### 5.2 Timing

| Taxa | Best Time | Season |
|------|-----------|--------|
| Plants | When in flower or fruit | Wet season (peak biomass) |
| Birds | Early morning (06:00-09:00) or late afternoon | Breeding season for species richness |
| Insects | Warm days, 10:00-15:00 | Dry season (higher activity) |
| Mammals | Dawn/dusk, or camera traps 24h | Year-round |
| Amphibians | After rain, evening | Wet season |
| Reptiles | Mid-morning, sunny days | Dry season, warm months |

### 5.3 Identification

- Use **regional field guides** or mobile apps (iNaturalist, Merlin for birds, Seek for plants)
- **Photograph unknown species** from multiple angles (top, side, close-up of flowers/leaves)
- Record **abundance** using standardized scale:
  - Rare: <1 individual per survey
  - Occasional: 1-5 individuals
  - Frequent: 6-20 individuals
  - Common: 21-50 individuals
  - Abundant: >50 individuals
- For insects: collect **voucher specimens** in ethanol if identification uncertain
- Record observer confidence: confirmed / probable / possible

### 5.4 Data Entry

1. Create `species_observation` record per species per plot
2. Set `species_category`: bird, insect, plant, mammal, amphibian, reptile, fish, fungi, other
3. Record `method`: visual, acoustic, camera_trap, transect, quadrat, pitfall, other
4. Attach photo URLs in `evidence_urls`
5. Compute Shannon diversity index (automated from species count data)

### 5.5 Frequency

| Phase | Frequency | Notes |
|-------|-----------|-------|
| Baseline | Comprehensive survey at project start | All methods, all taxa |
| Monitoring | Quarterly (wet + dry seasons minimum) | Match method to season |
| Event-triggered | After land use change, pest outbreak, or restoration activity | Compare to baseline |

---

## 6. Water Sampling Protocol

### 6.1 Sampling Design

- Identify water sources from `water_access` table
- Sample **upstream and downstream** if near waterways (minimum 50m apart)
- Include **irrigation return flow** if applicable
- GPS-tag each sampling point
- Sample from multiple depths if water body >2m deep

### 6.2 Collection Procedure

1. **Rinse sample bottle 3x** with sample water before collection
2. **Surface water**: collect from 15-30cm depth (not surface film)
3. **Groundwater**: use depth sampler or pump from well; discard first 2-3 bottle volumes (purge well)
4. **Fill bottle completely** — no air headspace (except for DO samples)
5. **For dissolved oxygen**: fix with manganese sulfate and alkaline reagent immediately
6. **For nutrients (N, P, K)**: preserve with 2ml concentrated H2SO4 per liter, or keep on ice
7. **For bacteria**: sterilize bottle, keep at 4°C, deliver to lab within 6 hours
8. **Record**: air temperature, water temperature, weather conditions, water appearance (color, odor, turbidity)
9. **Photograph** sampling location with GPS coordinates visible

### 6.3 Field Measurements (Before Preservation)

| Parameter | Instrument | Calibration | Acceptable Range |
|-----------|-----------|-------------|-----------------|
| pH | Portable pH meter | Buffer 4.0, 7.0, 10.0 | 4.0-10.0 |
| Electrical conductivity (EC) | Portable EC meter | 1.413 mS/cm standard | 0-5000 µS/cm |
| Dissolved oxygen | DO meter | Air-saturated water | 0-20 mg/L |
| Turbidity | Turbidity tube or meter | NTU standards | 0-1000 NTU |
| Water temperature | Digital thermometer | Ice point (0°C) | 0-50°C |

### 6.4 Chain of Custody

1. **Label each bottle**: sample ID, date, time, GPS coordinates, collector name
2. **Complete chain of custody form**: chain of custody starts at collection, ends at lab
3. **Transport in cooler** with ice packs (maintain 4°C)
4. **Deliver to lab within 24 hours** (6 hours for bacteria analysis)
5. **Sign transfer log** at collection and at lab delivery
6. **Photograph** samples at collection and at lab delivery

### 6.5 Lab Submission

- Request **standard water quality panel**: pH, EC, TDS, nitrate, phosphorus, potassium, dissolved oxygen, turbidity
- For **potability**: add coliform, E. coli, heavy metals (Pb, As, Hg, Cd)
- For **irrigation suitability**: add salinity, sodium adsorption ratio (SAR), boron
- Link `water_sample` to `water_analysis` when lab results arrive
- Set `evidence_maturity` based on lab verification

### 6.6 Data Entry

1. Create `water_sample` record with field measurements at time of collection
2. Link to `water_access` (source infrastructure)
3. When lab results arrive: create `water_analysis` record
4. Link: `water_sample.water_analysis_id → water_analysis.id`
5. Set `status = 'draft'` until lab results verified

### 6.7 Frequency

| Phase | Frequency | Notes |
|-------|-----------|-------|
| Baseline | Comprehensive panel at project start | Full chemistry + microbiology |
| Monitoring | Quarterly (or monthly for irrigation sources) | Standard panel |
| Dry season | Additional sampling | Concentration effects |
| After rain events | Sample runoff for 24-48 hours | Sediment and nutrient flush |
| Contamination incident | Immediate + follow-up at 24h, 72h, 7 days | Full panel including bacteria |

---

## 7. Weather Observation Protocol

### 7.1 On-Site vs API Data

- **Primary source**: OpenWeatherMap API (automated, every 6 hours)
- **Supplementary**: On-site instruments for microclimate data
- **Reconciliation**: Compare API vs on-site readings monthly; document discrepancies

### 7.2 On-Site Station Placement

- **Location**: Open area, 2m above ground level
- **Clearance**: 10m minimum from buildings, trees, and heat sources
- **Rain gauge**: 30cm above ground, level surface, unobstructed (no overhanging branches)
- **Thermometer**: Shaded, ventilated radiation shield (Stevenson screen or equivalent)
- **Orientation**: Rain gauge rim horizontal; thermometer vertical; wind instruments face north

### 7.3 Manual Readings

1. **Read at the same time daily** (recommend 08:00 or 18:00 local time)
2. **Max/min thermometer**: Read and record; reset by shaking or pressing reset button
3. **Rain gauge**: Read measurement; record; empty into measuring cylinder if needed
4. **Hygrometer**: Read and record relative humidity
5. Enter all readings into `weather_observation` table with `source = 'manual'`

### 7.4 Data Entry

- Enter manual readings into `weather_observation`
- Include observer name and method in `notes`
- Cross-reference with API data for anomalies (e.g., API says 0mm rain but gauge shows 15mm)
- Set `source = 'manual'` to distinguish from automated API data

---

## 8. Harvest Measurement Protocol

### 8.1 Weighing

1. **Calibrate scale** monthly with certified weights (or weekly for high-value crops)
2. **Tare container weight** before loading (record container tare weight on data sheet)
3. **Weigh immediately after harvest** (fresh weight) — do not let produce dry before weighing
4. **Record to nearest 10g** (e.g., 23.450 kg)
5. For small quantities (<1kg): use hanging scale (1g resolution)
6. **Weigh rejected/lost produce separately** for loss tracking

### 8.2 Quality Grading

| Grade | Criteria |
|-------|----------|
| A (Premium) | >90% visually perfect, no defects, meets size/weight specs, no pest/disease damage |
| B (Standard) | 70-90% quality, minor cosmetic defects, acceptable size, minor pest marks |
| C (Below standard) | 50-70% quality, significant defects, undersized, visible disease/pest damage |
| Rejected | <50% quality, food safety issues, structural damage, mold/rot |

- Use **visual reference board** with grade-specific photos for consistent grading
- Different crops have different grading standards — maintain crop-specific reference boards
- Record grading decision and notes on data sheet

### 8.3 Loss Measurement

1. Weigh rejected/lost produce separately from marketable produce
2. Record **loss reason**: pest, disease, mechanical damage, weather (wind/rain/hail), spoilage, overripe, unharvested
3. Estimate **loss value** using current market price (from `price_observation` table)
4. Enter in `harvest_event`: `loss_amount`, `loss_unit`, `loss_reason`, `loss_estimated_value`

### 8.4 Post-Harvest Handling

Record each handling step in `harvest_handling_record`:

1. **Cleaning**: Was produce washed/cleaned? Equipment cleaned between batches?
2. **Sorting**: By size, color, quality grade?
3. **Grading**: Grade A/B/C assignment?
4. **Drying**: Sun-dried, mechanical dryer, shade-dried? Target moisture content?
5. **Processing**: Cut, peeled, fermented, otherwise processed?
6. **Packaging**: Bulk, bagged, boxed? Material type?
7. **Storage**: Temperature controlled? Ventilated? Duration?
8. **Transport**: Vehicle type? Temperature maintained?

For each step, record:
- `organic_segregated`: Was organic produce kept separate from conventional?
- `equipment_cleaned`: Was all equipment cleaned before use?
- `contamination_risk`: Low / Medium / High (based on proximity to conventional, chemicals, etc.)

### 8.5 Moisture Content

1. Use **portable moisture meter** with crop-specific calibration
2. Take **10 representative samples** from the batch
3. Measure each sample; record average
4. Compare to **target moisture for storage** (varies by crop):
   - Maize: 12.5%
   - Rice (paddy): 14%
   - Beans: 12%
   - Cassava: 13%
   - Coffee: 11-12%
5. If moisture exceeds target: dry further before storage

### 8.6 Data Entry

1. Create `harvest_event` with `quantity`, `unit`, `quality_grade`, `destination`
2. Create `harvest_handling_record` for each handling step
3. Link to `crop_cycle` and `plot`
4. Attach photo evidence of harvest and grading
5. Verify with supervisor before setting `status = 'submitted'`

---

## 9. Pest Monitoring Protocol

### 9.1 Visual Scouting

1. Walk **systematic route** through plot (S-pattern or zigzag)
2. Inspect **10 plants per plot** (or 10% of plot, whichever is larger)
3. For each plant, record:
   - Pest type (insect, disease, weed)
   - Severity: 1 (trace), 2 (light), 3 (moderate), 4 (heavy), 5 (severe)
   - Plant part affected (leaf, stem, root, fruit, flower)
   - Natural enemies present (predators, parasitoids)
4. **Photograph** damage and pests (minimum 3 photos: wide shot, close-up, macro)
5. Note environmental conditions: temperature, humidity, recent weather

### 9.2 Trapping

| Trap Type | Quantity | Placement | Check Frequency | Replace Frequency |
|-----------|----------|-----------|-----------------|-------------------|
| Yellow sticky traps | 2-3 per plot | Canopy height, facing south | Weekly | Weekly |
| Blue sticky traps | 1-2 per plot | Canopy height (thrips-specific) | Weekly | Weekly |
| Pheromone traps | 1-2 per plot | 1m above ground, downwind edge | Weekly | Per lure schedule |
| Pitfall traps | 5 per plot, line | Flush with ground | Daily | Daily (during survey) |

### 9.3 Soil-Dwelling Pests

1. Take **soil core samples** (10cm diameter, 20cm deep) at 5 points per plot
2. **Sift through soil** on a white tray for visibility
3. Count and identify: larvae, pupae, root damage, nematode galls
4. Record: pest type, life stage, count, damage level (1-5)
5. Submit samples to entomologist if identification uncertain

### 9.4 Disease Scouting

1. Look for: leaf spots, wilting, yellowing, fungal growth, bacterial ooze, viral mottling
2. Record: disease name (or description), incidence (% of plants affected), severity (1-5)
3. Take leaf/tissue samples for lab analysis if pathogen is unknown
4. Note environmental conditions: humidity, temperature, rainfall in past 7 days

### 9.5 Data Entry

1. Create `pest_observation` record (from `047_ecological_modeling_v2`)
2. Enter severity, incidence, pest type, affected plant part
3. Attach photos in `evidence_urls`
4. Link to `crop_cycle` and `plot`
5. Enter `predation_rate_per_day` if natural enemies observed

---

## 10. Measurement Cadence Matrix

| Data Type | Frequency | Who Collects | Equipment | System Table | Evidence Level |
|-----------|-----------|-------------|-----------|-------------|---------------|
| Soil chemistry | Quarterly/Semi-annual | Field technician | Auger, sample bags, GPS | `soil_sample` | 1→4 (with lab) |
| Soil carbon | Semi-annual/Annual | Field technician | Auger, sample bags, GPS | `soil_carbon_measurement` | 1→4 (with lab) |
| Tree DBH | Quarterly (juvenile) / Semi-annual (mature) | Field worker | DBH tape, tree tags, GPS | `tree_measurement` | 1→2 |
| Tree height | Semi-annual/Annual | Field technician | Clinometer or hypsometer | `tree_measurement` | 1→2 |
| Canopy diameter | Semi-annual/Annual | Field worker | Measuring tape | `tree_measurement` | 1→2 |
| Soil moisture | Continuous (sensor) / Daily (manual) | Automated / Field worker | TDR meter or sensor | `sensor_reading` | 1→2 |
| Air temperature | Continuous (sensor) / Daily (manual) | Automated / Field worker | Thermometer or sensor | `sensor_reading` / `weather_observation` | 1→2 |
| Rainfall | Continuous (sensor) / Daily (manual) | Automated / Field worker | Rain gauge or sensor | `sensor_reading` / `weather_observation` | 1→2 |
| Biodiversity (plants) | Quarterly | Field technician | Quadrat, transect tape | `species_observation` | 1→2 |
| Biodiversity (birds) | Quarterly | Field technician / Community | Binoculars, point count | `species_observation` | 1→2 |
| Biodiversity (insects) | Monthly (traps) | Field worker | Sticky traps, pheromone traps | `species_observation` | 1→2 |
| Water quality | Quarterly | Field technician | Sample bottles, field kit | `water_sample` → `water_analysis` | 1→4 (with lab) |
| Water level | Continuous (sensor) | Automated | Water level sensor | `sensor_reading` | 1→2 |
| Harvest yield | Per harvest event | Field worker / Farmer | Scale, grading board | `harvest_event` | 1→2 |
| Harvest handling | Per handling step | Field worker | Checklists | `harvest_handling_record` | 1→2 |
| Pest scouting | Monthly (growing season) | Field worker | Visual inspection, traps | `pest_observation` | 1→2 |
| Weather (API) | Every 6 hours | Automated | OpenWeatherMap API | `weather_observation` | 1 |
| Remote sensing | Weekly (configurable) | Automated | GEE / Copernicus | `remote_sensing_observation` | 1 |

---

## 11. Data Quality & QA/QC

### 11.1 Range Validation

All readings are checked against `sensor_type` min/max values at ingestion time:

| Sensor Type | Min | Max | Unit |
|------------|-----|-----|------|
| Soil moisture | 0 | 100 | % |
| Soil temperature | -40 | 80 | °C |
| Air temperature | -50 | 60 | °C |
| Humidity | 0 | 100 | % |
| Light | 0 | 200000 | lux |
| Rainfall | 0 | 500 | mm |
| Water level | 0 | 10000 | cm |

Manual entries are checked against known physiological ranges:
- Soil pH: 3.0-9.0 (extreme range; most crops 5.5-7.5)
- Tree DBH: 0.5-500cm (realistic range)
- Species count: 0-500 per plot (survey-dependent)

### 11.2 Duplicate Detection

- Same `location_id` + same `sample_date` + same `sensor_type` = potential duplicate
- Review before submission; keep most recent, mark older as `rejected`
- System auto-detects via UNIQUE constraints where applicable

### 11.3 Observer Calibration

- **New observers**: train with experienced observer for 2-3 sessions before independent work
- **Inter-observer reliability**: 10% of plots measured by 2 observers independently
- **Acceptable agreement**: Cohen's kappa > 0.6 (substantial agreement)
- **Recalibrate annually** or when new crop types are introduced

### 11.4 Chain of Custody

- Lab samples: unique ID, signed transfer log from field to lab
- GPS-tag at collection AND at lab delivery
- Photograph samples at collection point and at lab reception
- Store chain of custody in `water_sample.chain_of_custody` or `soil_sample.notes`

### 11.5 Evidence Maturity Escalation

| Level | Trigger | Action |
|-------|---------|--------|
| 1 → 2 | GPS + photos attached | Auto-upgrade when evidence_urls populated |
| 2 → 3 | Supervisor review | Manual verification via Directus workflow |
| 3 → 4 | Lab report attached | Link lab report URL; auto-upgrade |
| 4 → 5 | On-chain attestation | Publish via EAS attestation service |
| 5 → 6 | External verifier sign-off | External verification + methodology reference |

---

## 12. Sample Plot Design

### 12.1 Plot Types

| Type | Dimensions | Best For |
|------|-----------|---------|
| Fixed circular | Radius 5-20m | Forest, agroforestry, tree crops |
| Fixed rectangular | 10x10m (dense) or 20x20m (open) | Cropland, grassland |
| Nested plots | Large (20x20m) + small (2x2m) within | Multi-strata vegetation |

### 12.2 Layout

- Use `sample_plot_design` table for statistical plot placement
- **Minimum 5 plots per zone** for statistical validity
- **Minimum distance between plots**: 10m (configurable in `min_distance_between_plots_m`)
- **GPS-tag plot center**, mark with permanent stake (metal or concrete)
- Use `sampling_method`: `simple_random`, `stratified_random`, or `systematic_grid`

### 12.3 Establishment Procedure

1. Generate plot locations using `sample_plot_generator` (statistical placement)
2. Navigate to each GPS point
3. Clear 2m radius around center stake
4. Measure and mark plot boundary with colored tape or stakes
5. **Photograph plot** from center in 4 cardinal directions (N, E, S, W)
6. Record in `sample_plot` table with center GPS and plot dimensions
7. Create `sample_plot_design` record with design parameters

### 12.4 Re-measurement Protocol

1. Navigate to plot center using GPS (expect ±3m accuracy)
2. Locate permanent stake or re-establish from GPS
3. Re-mark boundary if stakes moved or tape degraded
4. Measure all variables per the relevant protocol (soil, tree, biodiversity)
5. Update `sample_plot` with `last_measurement_date`
6. Compute `next_measurement_due` based on `measurement_frequency`

### 12.5 Permanence Rules

- Plots are **permanent** for the life of the project
- If a plot must be moved (e.g., infrastructure construction): create new plot, link to old via `metadata` JSONB
- **Never delete permanent plots** — only supersede (set status to `superseded`)
- Maintain historical records for all re-measurements

---

## 13. MRV Ground-Truthing

### 13.1 Field-to-Digital Pipeline

```
Field Worker → Data Sheet / Mobile App → Directus Entry → Governed Lifecycle
     ↓                    ↓                    ↓                    ↓
GPS-tagged         Structured form      PostgreSQL table     draft → submitted
observation        with required        with source lineage  → verified → published
                   fields
```

1. Field worker collects data using equipment per protocol
2. Enters data via Directus web form or CSV upload (via spreadsheet bridge)
3. Data enters `draft` status with `source_system = 'field_collection'`
4. GPS coordinates, photos, and observer name auto-attached
5. Supervisor reviews and sets `status = 'submitted'`
6. Manager verifies and sets `status = 'verified'` (or `rejected` with reason)

### 13.2 Reconciliation with Remote Sensing

| Field Measurement | Remote Sensing Equivalent | Reconciliation Method |
|-------------------|--------------------------|----------------------|
| Tree DBH/height/canopy | NDVI, canopy cover, canopy height | Compare biomass estimates from both sources |
| Soil carbon (lab) | SOC prediction model | Compare lab result with model prediction |
| Biodiversity count | NDVI as proxy for vegetation health | Correlate species richness with vegetation indices |
| Weather (on-site) | OpenWeatherMap API | Compare temperature, rainfall readings |
| Pest observation | NDVI decline, pest hotspot | Correlate pest severity with vegetation stress |

### 13.3 Community MRV

- Community members can submit observations via mobile or Directus
- All community data enters at **Level 1** (self-reported)
- Requires **supervisor verification** for Level 2+ (GPS + photos must be present)
- Privacy: community data is private by default; public only with `consent_given = TRUE`

### 13.4 Evidence Escalation Path

```
Level 1: Field entry submitted (GPS + basic data)
    ↓
Level 2: Structured data with GPS + photos
    ↓
Level 3: Reviewed by supervisor
    ↓
Level 4: Lab report or evidence attached (public claim allowed)
    ↓
Level 5: Attested on-chain via EAS (carbon claims possible)
    ↓
Level 6: Externally verified with methodology reference (public carbon claims)
```

---

## 14. Equipment Maintenance

### 14.1 Calibration Schedules

| Equipment | Calibration Method | Frequency | Acceptable Drift |
|-----------|-------------------|-----------|-----------------|
| pH meter | Buffer solutions pH 4.0, 7.0, 10.0 | Weekly | ±0.1 pH |
| EC meter | 1.413 mS/cm NaCl standard | Monthly | ±5% |
| Moisture meter | Oven-dried soil sample comparison | Monthly | ±2% |
| Scale | Certified calibration weights | Monthly | ±10g (50kg scale) |
| DBH tape | Check against steel ruler | Annually | ±1mm |
| Clinometer | Check against known height object | Annually | ±0.5° |
| Rain gauge | Measure collected water volume | Quarterly | ±5% |
| DO meter | Air-saturated water calibration | Before each use | ±0.5 mg/L |

### 14.2 Battery Management

| Device | Battery Type | Check Frequency | Replace When |
|--------|-------------|----------------|-------------|
| GPS device | Rechargeable Li-ion | Weekly | <20% capacity |
| Camera trap | AA lithium (8-12x) | Monthly | <20% capacity |
| Weather station | 12V lead-acid or solar | Monthly | <30% capacity |
| pH meter | 9V alkaline or rechargeable | Weekly | Low battery indicator |
| DO meter | Rechargeable | Before each use | Low battery indicator |

### 14.3 Sensor Cleaning

| Equipment | Cleaning Method | Frequency |
|-----------|----------------|-----------|
| pH electrode | Rinse with distilled water; store in KCl solution | After each use |
| EC electrode | Soak in DI water | Weekly |
| Rain gauge | Remove debris; flush with clean water | Monthly |
| Tipping bucket | Clean funnel, check mechanism | Quarterly |
| Camera trap lens | Clean with lens cloth | Monthly |
| Soil auger | Wash with water, dry, oil lightly | After each use |

### 14.4 Replacement Schedules

| Equipment | Replacement Trigger | Expected Lifespan |
|-----------|-------------------|-------------------|
| pH electrode | Calibration drift >0.2 pH or age >1 year | 12 months |
| Sticky traps | After each weekly check | 1 week |
| Sample bottles | Single-use for lab submission | 1 use |
| Tree tags | If damaged or lost; never reuse numbers | 5-10 years |
| GPS batteries | When capacity <20% | 2-3 years |
| Clinometer | If calibration fails or lens damaged | 5-10 years |
| DBH tape | If stretched or markings fade | 3-5 years |
