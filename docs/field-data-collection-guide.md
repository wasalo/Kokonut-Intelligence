# Field Data Collection Guide

This guide describes how field observations map to Kokonut Intelligence records,
what the software actually validates, and which practices remain local SOP
recommendations. It is not a universal agronomy protocol. Farms must adapt
equipment, sampling frequency, safety procedures, units, and laboratory methods
to local conditions and approved methodology.

## Implementation Status Labels

| Label | Meaning |
|-------|---------|
| **Implemented** | Enforced by schema, service, hook, or tested ingestion path |
| **Partially implemented** | Supported for some routes or collections only |
| **Recommendation** | Field practice suggested by this guide; not software-enforced |
| **Not implemented** | Do not represent this as an available workflow |

The canonical storage layer is PostgreSQL. Directus is the API/admin layer;
ClickHouse mirrors selected high-volume events. Computed metrics and model
outputs are drafts until separately verified. An attachment, GPS coordinate,
model result, or attestation does not automatically verify a field record.

## Canonical Data-Entry Routes

### Directus

Directus is the primary user-facing route for collections that have configured
permissions and workflow hooks. Lifecycle hooks cover selected collections such
as `farm_activity`, `harvest_event`, `mrv_claim`, `data_stream_post`, and
stakeholder collections. The following field tables do not all have the same
Directus lifecycle hooks:

- `soil_sample`
- `soil_carbon_measurement`
- `tree_record`
- `tree_measurement`
- `species_observation`
- `water_sample`
- `water_analysis`
- `weather_observation`
- `sensor_reading`
- `pest_observation`
- `harvest_handling_record`

Do not assume Directus automatically attaches GPS, photos, observer names,
source lineage, or evidence. Accountability comes from server-side
`meta.accountability`, not client-supplied payload fields.

### Sensor Ingestion

| Route | Behavior |
|-------|----------|
| CSV/manual sensor CLI | Range validation; out-of-range values become `suspect`; duplicate identity uses sensor/date/time |
| HTTP receiver | HMAC-authenticated JSON sensor ingestion; does not use all CSV validation or consistently populate source lineage |
| MQTT subscriber | Registered devices, topic identity, HMAC/TLS/broker controls; device registration is separate |
| Weather API | OpenWeatherMap current observations; deployment crontab runs weather every six hours |
| Sensor device manager | Device registration, health, and configuration; not a field-observation form |

Sensor duplicate identity is `(sensor_id, reading_date, reading_time)` where
the schema supports it. CSV/API insertion uses `ON CONFLICT DO NOTHING`.
HTTP/MQTT paths do not consistently populate `source_system`, `source_id`, or
`source_raw` on `sensor_reading`.

### Spreadsheet Bridge

`services/export/spreadsheet_bridge.py` supports:

- `farm_activity` CSV import/export;
- EBF scorecard metadata import;
- EBF evidence-link validation;
- dry-run import behavior.

It does not generically import soil, tree, biodiversity, water, harvest, pest,
sensor, or weather records. Farm activity imports begin as draft records. EBF

### Spatial Import

`services/export/spatial_import.py` imports GeoJSON/KML polygon features into
`farm_zone` and writes `spatial_import_log`. It is not a general importer for
trees, sample plots, soil, sensors, water points, or field observations. It can
skip or overwrite existing zone keys according to import options.

### Mobile Offline Queue

The mobile/offline subsystem supports device registration, GPS/photo references,
form payloads, queueing, duplicate `client_id` detection, conflict handling,
and sync logs. Its queue stores arbitrary payloads in `offline_collection` and
marks them synced; it does **not** transform payloads into
`soil_sample`, `tree_record`, `pest_observation`, or other canonical field rows.
There is no documented production mobile application in this repository.

### Data Stream

`data_stream_post` is a governed chronological evidence-post system. It is not a
generic ingestion adapter for every field table. Use it for field updates,
monitoring reports, photos, and related evidence narratives; use domain tables
for structured measurements.

## Evidence Maturity And Lifecycle

The canonical maturity reference is `evidence_maturity_level`:

| Level | Meaning |
|---:|---|
| 0 | Narrative only |
| 1 | Self-reported record |
| 2 | Structured record |
| 3 | Reviewed record |
| 4 | Evidence-linked record |
| 5 | On-chain or off-chain attested record |
| 6 | Externally verified with methodology and verifier reference |

The guide’s former automatic escalation rules are not implemented. The system
does not generally upgrade maturity when GPS, photos, lab URLs, or attestations
are added. Maturity is explicitly assigned or updated through collection-
specific governance paths.

Lifecycle and maturity are separate. Selected governed records use:

```text
draft → submitted → verified → published
                  ↘ rejected
```

This state machine is not universal across every field table. For example,
or maturity fields.

Public carbon claims require maturity 6 plus claim type, verifier, methodology,
publication, registry, and evidence conditions. Ordinary field data should not
be described as a public claim merely because it reached Level 4.

## Privacy And Consent

Privacy controls are collection-specific:

- Stakeholder feedback uses explicit consent, public consent scope, published
  status, and a non-empty public summary.
- Community data entered into `species_observation` is not automatically
  consent-gated merely because it is community-collected.
- Most soil, tree, water, pest, weather, and sensor tables do not have consent
  columns.
- Directus accountability identifies the server-side actor; it does not make a
  field-worker identity public by default.
- Public tree views omit exact tree GPS, but may expose aggregate spatial maps.
- The published water sample view can expose GPS and collector fields when its
  publication conditions are met. Sensitive water-source coordinates therefore
  require a separate access policy; the database does not guarantee restriction
  by default.
- Lab evidence should remain off-chain as a URL, CID, or hash where the owning
  schema supports those fields. Do not store private laboratory bodies in
  public payloads.

## Table Contracts

### Soil

`soil_sample` is defined in `005_environmental.sql` and extended by
`080_field_collection.sql` and `095_soil_protocol.sql`. Required location,
plot, and sample-date fields are enforced. Field collection additions include
GPS, collector, photo, chain-of-custody, and lab-report metadata where supported.

`soil_carbon_measurement` stores before/after carbon measurements, baseline
status, evidence URLs/hashes, lifecycle, and maturity fields after migrations.
It does not use the same `lab_report_url` contract as `soil_sample`.

**Recommended practice, not universal enforcement:** define a sampling design,
use representative subsamples, avoid edges and disturbed areas, label samples,
preserve chain of custody, and submit to a qualified lab within the lab’s
specified time window. Sampling count, depth, frequency, and analysis panel are
configured in `sampling_protocol` or local SOPs; the software does not enforce
five composite samples for every zone.

### Trees

`tree_record` and `tree_measurement` are defined in
`schemas/postgres/057_tree_tracking.sql`.

| Record | Key fields |
|--------|------------|
| `tree_record` | plot/location, species, tree tag, latitude/longitude, planting date, height, DBH, canopy, health, biological status |
| `tree_measurement` | tree ID, measurement date, height, DBH, canopy, health |

Tree health is constrained to 0–100. Tree maturity and status values are
constrained. `(plot_id, tree_tag)` is the relevant tree identity. `source_raw`
is text in this schema, not JSONB.

**Recommended practice:** measure DBH at a consistent reference height, record
height and canopy axes consistently, retain tags, and record the allometric
equation in `tree_inventory.allometric_source` when preparing carbon estimates.
There is no automatic trigger that updates aggregate `tree_inventory` rows from
tree records or measurements.

### Biodiversity

`species_observation` stores species, category, count, method, plot/location,
and optional evidence. Later migrations add:

- `trophic_level`
- `population_density_per_m2`
- `conservation_status`
- `status`
- lifecycle/maturity fields where applicable

Supported survey methods and sampling design are constrained by the schema where
defined, but quadrat counts, transect length, point-count duration, camera-trap
deployment, and seasonal cadence are local SOP recommendations.

Do not imply that unknown species identification, Shannon-index calculation, or
observer-confidence values are automatically completed by the database.

### Water

`water_access` is infrastructure metadata, not a governed sample record. It does
not have the same evidence, maturity, consent, or source-lineage fields as
`water_sample`.

`water_sample` supports field collection metadata, GPS, photos, chain-of-custody,
lifecycle, maturity, and source fields. `water_analysis` stores laboratory or
analytical results with lifecycle/source fields but no evidence-maturity field.
Water sample type is constrained to values such as `surface`, `groundwater`,
`irrigation`, `runoff`, `rainwater`, and `other`.

**Recommended practice:** calibrate field meters, record temperature and sample
conditions, preserve samples according to laboratory requirements, and retain
transfer records. Signed lab handoff, delivery photographs, and six-hour
bacterial transport are not automatically enforced by the platform.

### Weather

`weather_observation` stores observations from API or manual sources. It uses a
`source` field and is distinct from `weather_forecast` records. OpenWeatherMap
ingestion is scheduled every six hours by deployment configuration, but cadence
is not a database constraint and API/manual observations are not automatically
reconciled.

Manual data should record method and observer context in available fields. The
platform does not automatically guarantee a daily reading time or API-versus-
station discrepancy review.

### Harvest And Handling

`harvest_event` requires crop-cycle, plot, location, date, quantity, and unit
fields. Quantity is non-negative and loss fields support separate loss tracking.
Use a scale, tare containers, record marketable/rejected quantities separately,
and attach quality evidence according to the local crop protocol.

`harvest_handling_record` supports handling type, organic segregation, equipment
cleaning, contamination risk, and organic lot details. It does not have the
same lifecycle or maturity fields as a harvest event. It is not automatically
verified when a harvest event is submitted.

### Pest

`pest_observation` is defined in `047_ecological_modeling_v2.sql` and extended
by migration 050. It stores pest species/category, incidence, severity, weather,
predators, natural enemies, predation count, and predation rate.

Severity is the constrained enum:

```text
none, low, medium, high, critical
```

It is not a numeric 1–5 field. Pest category values are also constrained.
Scouting routes, number of plants, trap density, inspection frequency, and
photographic minimums are recommended SOP values, not universal database rules.

## Sensors And QA/QC

Sensor types define configured minimum and maximum values. CSV/API sensor
ingestion marks out-of-range values as `suspect`; it does not necessarily reject
them. HTTP/MQTT behavior does not perform exactly the same range checks.

The platform supports sensor alert rules, quality fields, duplicate identity,
device health, freshness checks, HMAC authentication, and selected ClickHouse
mirrors. It does not enforce the following general field SOP claims:

- physiological pH, DBH, or species-count ranges for all manual entries;
- two-observer measurement percentages;
- Cohen’s kappa thresholds;
- annual observer recalibration;
- review and rejection of every suspected duplicate;
- GPS capture at laboratory delivery;
- automatic `next_measurement_due` calculation.

Do not replace missing values with estimates without labeling the estimate. The
platform supports explicit estimated/suspect quality states and missingness
should remain visible for review.

### Duplicate Rules

Duplicate behavior is table-specific:

| Entity | Relevant identity rule |
|--------|------------------------|
| `sensor_reading` | sensor/date/time unique where enforced |
| `tree_record` | plot/tree tag unique |
| `sample_plot` | design/plot number unique |
| `sampling_protocol` | location/protocol key unique |
| Mobile queue | optional `client_id` duplicate detection |
| Spatial zones | zone-key skip/overwrite behavior |

There is no universal `location_id + sample_date + sensor_type` duplicate rule.

## Sample Plot Design And Spatial Data

`sample_plot_design` and `sample_plot` are defined in
`schemas/postgres/071_sample_plot_design.sql`. Designs constrain sampling
method/status, and generated plots link to design, farm zone, location, plot
number, and center coordinates. `sample_plot` is not a foreign key to the
ordinary `plot` table.

The sample-plot generator exists, but its method and minimum-distance behavior
should be treated as implementation details, not a guarantee of statistical
validity. It may relax distance constraints when necessary.

The spatial importer creates `farm_zone` polygons and logs imports. It does not
import individual trees, soil points, sensors, water samples, or sample plots.

## Evidence And MRV Pipeline

```text
field worker / sensor / provider
        ↓
Directus, sensor ingestion, or domain-specific import
        ↓
draft or source-specific canonical record
        ↓ human/service-specific review
submitted → verified → published where that table supports the lifecycle
        ↓
metric, claim, report, or optional EAS payload
```

The exact path depends on the collection. Do not claim that every field table
passes through Directus or the same lifecycle.

Community data is not automatically consented for publication. Public claims,
carbon outputs, and EBF outputs have additional maturity, evidence, verifier,
registry, and public-safe gates. See `docs/evidence-maturity.md`.

## Recommended Field Practice

The following are recommendations, not universal software constraints:

- Use calibrated instruments appropriate to the measurement.
- Record units, local time, plot/location, observer, method, and conditions.
- Preserve sample IDs and chain-of-custody information for laboratory material.
- Photograph evidence without exposing restricted people or locations.
- Use consistent species names and controlled vocabulary values.
- Record missingness and uncertainty instead of silently inventing values.
- Submit field records promptly, but do not interpret a time target as an SLA
  enforced by the platform.
- Review source data before setting a governed record to verified or published.
- Maintain local safety procedures for chemicals, samples, wildlife, water, and
  field travel; this guide does not replace occupational or laboratory safety.

## Tests And References

Relevant tests include:

- `tests/test_iot_sensor_push.py`
- `tests/test_spreadsheet_bridge.py`
- `tests/test_spatial_import.py`
- `tests/test_mobile_offline.py`
- `tests/test_data_governance.py`
- `tests/test_organic_certification.py`
- `tests/test_tree_tracking.py`
- `tests/test_sample_plot_generator.py`
- `tests/test_ecological_modeling.py`
- `tests/test_ecological_modeling_v2.py`
- `tests/test_documentation_consistency.py`

Primary schema references:

- `schemas/postgres/005_environmental.sql`
- `schemas/postgres/019_module_b_gaps.sql`
- `schemas/postgres/026_ground_analytics.sql`
- `schemas/postgres/028_carbon_framework.sql`
- `schemas/postgres/029_impact_accountability_foundation.sql`
- `schemas/postgres/047_ecological_modeling_v2.sql`
- `schemas/postgres/055_organic_certification.sql`
- `schemas/postgres/057_tree_tracking.sql`
- `schemas/postgres/071_sample_plot_design.sql`
- `schemas/postgres/080_field_collection.sql`
- `schemas/postgres/095_soil_protocol.sql`
- `schemas/postgres/139_mobile_offline.sql`

Primary service references:

- `services/ingestion/sensor_ingester.py`
- `services/ingestion/http_sensor_receiver.py`
- `services/ingestion/mqtt_subscriber.py`
- `services/export/spreadsheet_bridge.py`
- `services/export/spatial_import.py`
- `services/analytics/mobile_offline.py`
- `services/agents/safety.py`
