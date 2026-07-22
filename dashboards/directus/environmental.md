# Environmental Monitoring Dashboard

## Overview

Environmental monitoring dashboard for weather data, sensor readings, NDVI trends, soil carbon measurements, and ecological alerts.

## Setup

1. In Directus Admin → Settings → Roles → Assign to Analyst, Manager, or Auditor roles
2. Read-only access to environmental collections
3. Location-scoped via `assigned_locations`

## Modules

### 1. Weather Summary (Stats Row)

**Type:** Stats  
**Collection:** `weather_observation`  
**Filters:** Last 7 days

**Metrics:**
- Average `temperature_c`
- Sum of `precipitation_mm`
- Average `humidity_pct`

### 2. Sensor Readings (Table)

**Type:** Table  
**Collection:** `sensor_reading`  
**Filters:** Last 24 hours

**Columns:** `sensor_type`, `value`, `unit`, `reading_date`, `quality`

### 3. NDVI Trend (Line)

**Type:** Line  
**Collection:** `remote_sensing_observation`  
**X-axis:** `observation_date` (monthly)  
**Y-axis:** Average `ndvi`  
**Filters:** Last 6 months

### 4. Soil Carbon (Table)

**Type:** Table  
**Collection:** `soil_carbon_measurement`

**Columns:** `measurement_date`, `depth_cm`, `carbon_pct`, `organic_matter_pct`, `method`

### 5. Sensor Alerts (Table)

**Type:** Table  
**Collection:** `sensor_alert`  
**Filters:** Open/acknowledged alerts

**Columns:** `severity`, `message`, `reading_value`, `triggered_at`

## Data Access Rules

```json
{
  "weather_observation": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "sensor_reading": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "remote_sensing_observation": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "soil_carbon_measurement": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  }
}
```

## Notes

- Sensor data refreshes via cron job
- NDVI from remote sensing automation
- Soil carbon measurements from field samples
