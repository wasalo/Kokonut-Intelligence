# Analyst Dashboard

## Overview

Read-only dashboard for data analysts to explore metric definitions, computed values, forecasts, dashboard datasets, and report snapshots.

## Setup

1. In Directus Admin → Settings → Roles → Use existing "Analyst" role (`a1000000-0000-0000-0000-000000000005`)
2. Verify permissions in `config/directus/permissions.sql`
3. Read-only access to all verified/published data

## Modules

### 1. Metric Catalog (Table)

**Type:** Table  
**Collection:** `metric_definition`  
**Filters:** `status` = `active`

**Columns:** `metric_key`, `name`, `category`, `unit`, `formula`  
**Sort:** `category`, `name`

### 2. Latest Metrics (Table)

**Type:** Table  
**Collection:** `metric_value`  
**Filters:**
- `location_id` = assigned location
- `status` IN (`verified`, `published`)

**Columns:** `metric_definition_id.metric_key`, `value`, `unit`, `period_end`, `verified`

### 3. Forecast Scenarios (Table)

**Type:** Table  
**Collection:** `forecast_scenario`  
**Filters:** `location_id` = assigned location

**Columns:** `scenario_name`, `created_at`, `status`, `description`

### 4. Dashboard Datasets (Table)

**Type:** Table  
**Collection:** `dashboard_dataset`  
**Filters:** `status` = `published`

**Columns:** `dataset_key`, `name`, `category`, `last_refreshed_at`

### 5. Report Snapshots (Table)

**Type:** Table  
**Collection:** `report_snapshot`  
**Filters:**
- `location_id` = assigned location
- `status` IN (`verified`, `published`)

**Columns:** `report_type`, `generated_at`, `status`, `location_id.name`

## Data Access Rules

```json
{
  "metric_definition": {
    "read": true
  },
  "metric_value": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "forecast_scenario": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "dashboard_dataset": {
    "read": true
  },
  "report_snapshot": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  }
}
```

## Notes

- Analysts have read-only access across all locations
- Cannot modify metrics, forecasts, or reports
- Useful for cross-location analysis and benchmarking
