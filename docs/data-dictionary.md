# Data Dictionary

## Governed Metric Definitions

| Metric Key | Display Name | Formula | Source Tables | Update Freq |
|-----------|-------------|---------|--------------|-------------|
| `crop_revenue` | Crop Revenue | SUM(sales_event.total_amount) WHERE verified | sales_event, crop_cycle | Daily |
| `net_crop_revenue` | Net Crop Revenue | crop_revenue - returns - discounts | sales_event, crop_cycle | Daily |
| `direct_crop_cost` | Direct Crop Cost | SUM(expense) WHERE direct allocation | expense_event, crop_cycle | Daily |
| `allocated_shared_cost` | Allocated Shared Cost | SUM(crop_cost_allocation.allocated) | crop_cost_allocation | Daily |
| `crop_noi` | Crop NOI | net_revenue - direct_costs - allocated_costs | noi_snapshot, crop_cycle | Daily |
| `loss_rate_pct` | Loss Rate % | 1 - (net_harvest / gross_harvest) | harvest_event | Daily |
| `operating_margin_pct` | Operating Margin % | crop_noi / net_revenue * 100 | noi_snapshot | Daily |
| `baseline_revenue` | Baseline Revenue | location.baseline_revenue | location | Once |
| `baseline_asset_value` | Baseline Asset Value | location.baseline_asset_value | location | Once |
| `baseline_cash_flow` | Baseline Cash Flow | location.baseline_cash_flow | location | Once |
| `value_flowed` | Value Flowed | SUM(verified, non-excluded flows) | value_flow_event | Weekly |
| `wallet_retention` | Wallet Retention | Active in current + prior period | wallet_activity_event | Monthly |
| `digital_lego_usage` | Digital Lego Usage | COUNT(distinct verified protocols) | digital_lego_usage | Weekly |
| `soil_carbon_delta` | Soil Carbon Delta | after_carbon - baseline_carbon | soil_carbon_measurement | Quarterly |
| `biodiversity_delta` | Biodiversity Delta | after_count - baseline_count | species_observation | Quarterly |
| `attestation_coverage` | Attestation Coverage | attested / eligible * 100 | attestation_record | Monthly |

## Core Entity Glossary

### Master Data

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `location` | Physical or ecosystem unit | name, slug, boundary, baseline_* |
| `farm` | Operational farm entity | location_id, farm_type, total_area |
| `plot` | Operational land subdivision | farm_id, area, soil_type, water_source |
| `crop` | Crop type and variety | name, variety, crop_category |
| `crop_cycle` | Crop-specific production cycle | plot_id, crop_id, planting_date, status |
| `partner` | Institution, buyer, funder, vendor | name, partner_type |
| `infrastructure_asset` | Physical infrastructure | location_id, asset_type, capacity |
| `staff` | Workers and team members | location_id, role |

### Operational Facts

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `farm_activity` | General field activity log | activity_type, activity_date, status |
| `harvest_event` | Quantity harvested | quantity, unit, quality_grade, loss_* |
| `sales_event` | Sales transaction | buyer, quantity, total_amount, payment_status |
| `expense_event` | Expense record | category, amount, allocation_method, status |
| `loss_event` | Loss/incident record | loss_type, quantity, estimated_value |
| `labor_event` | Labor hours and cost | hours_worked, hourly_rate, role |
| `field_note` | Qualitative observations | note_type, content, images |

### Financial Facts

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `financial_transaction` | Canonical cash/crypto transaction | transaction_type, amount, currency |
| `expense_category` | Governed expense taxonomy | name, code, is_direct |
| `crop_cost_allocation` | Shared cost allocation | allocation_method, allocated_amount |
| `value_flow_event` | Governed value-flow record | flow_type, amount, verified |
| `noi_snapshot` | Crop/farm/location NOI output | noi, operating_margin_pct |
| `cash_flow_snapshot` | Periodic cash-flow reporting | net_cash_flow, running_balance |

### Environmental

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `soil_sample` | Soil test | ph, organic_matter_pct, nutrients |
| `soil_carbon_measurement` | Before/after carbon | carbon_tonnes_per_ha, is_baseline |
| `species_observation` | Biodiversity count | species_name, count, method |
| `remote_sensing_observation` | NDVI/NDRE | ndvi, ndre, canopy_cover_pct |
| `weather_observation` | Weather data | temperature_c, precipitation_mm |
| `sensor_type` | Sensor type definition | code, name, default_unit, default_min, default_max |
| `sensor_device` | Registered sensor device | device_id, sensor_type_id, location_id, model, status |
| `sensor_reading` | Device reading | sensor_id, value, unit, quality, anomaly_flag |
| `alert_rule` | Threshold-based rule | sensor_type_id, operator, threshold, severity, cooldown_minutes |
| `sensor_alert` | Triggered alert | alert_rule_id, reading_id, severity, status |
| `mrv_claim` | Structured verification claim | claim_type, claim_data, status |

### Web3 & Attestation

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `wallet_profile` | Wallet identity | address, chain, role |
| `wallet_activity_event` | Chain transaction | tx_hash, activity_type, value |
| `digital_lego_usage` | Protocol interaction | protocol_id, action_type, amount |
| `attestation_schema` | EAS schema definition | schema_uid, chain, schema_text |
| `attestation_record` | Verification attestation | attestation_uid, status, claim_data |
| `treasury_event` | Token flow | flow_direction, amount, token |
| `chain_indexer_status` | Ingestion health tracking | chain, indexer_type, last_synced_block |

### Ingestion & Observability

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `price_observation` | Commodity price data | commodity_code, price_date, price_per_unit, source |
| `ingestion_log` | External data fetch log | source_system, target_table, status, processing_time_ms |
| `workflow_history` | State transition audit | entity_type, entity_id, from_state, to_state, changed_by |
| `approval` | Approval records | entity_type, entity_id, decision, decided_by |
| `file_upload` | Uploaded files | filename, storage_path, mime_type |

### Modeled Outputs

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `forecast_scenario` | Scenario assumptions | scenario_type, assumptions |
| `forecast_output` | Forecast result | metric_name, value, confidence_* |
| `metric_definition` | Governed semantic metric | metric_key, formula, version |
| `report_snapshot` | Frozen report output | report_data, snapshot_hash |
| `ai_summary` | Agent-generated narrative | content, source_record_ids |
