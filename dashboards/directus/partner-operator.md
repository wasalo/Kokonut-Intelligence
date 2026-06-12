# Partner Dashboard — Operator View

## Overview

This dashboard provides farm managers/operators with a comprehensive
view of operations, MRV data, and performance metrics.

## Setup

1. In Directus Admin → Settings → Roles → Create "Operator" role
2. Grant full access to operational collections
3. This is the primary daily-use dashboard

## Modules

### 1. Operations Overview (Stats Row)

**Type:** Stats (4 widgets)
**Collections:**

| Widget | Collection | Metric |
|--------|-----------|--------|
| Active Cycles | `crop_cycle` | COUNT WHERE status = 'active' |
| Pending Tasks | `farm_activity` | COUNT WHERE status = 'draft' |
| This Month Revenue | `sales_event` | SUM(total_amount) WHERE sale_date >= first_of_month |
| Alerts | `sensor_alert` | COUNT WHERE status = 'open' |

### 2. Activity Timeline (Timeline)

**Type:** Timeline
**Collection:** `farm_activity`
**Filters:**
- `location_id` = assigned location
- Last 30 days
**Sort:** `activity_date` DESC

### 3. Crop Cycle Status (Table)

**Type:** Table
**Collection:** `crop_cycle`
**Filters:** `location_id` = assigned location
**Columns:** `cycle_name`, `crop_id.name`, `planting_date`, `expected_harvest_date`, `status`, `actual_yield`

### 4. Sensor Dashboard (Series)

**Type:** Series (Multiple)
**Collection:** `sensor_reading`
**Filters:**
- `location_id` = assigned location
- Last 7 days
**Series:** Group by `sensor_type`

### 5. Weather History (Line Chart)

**Type:** Line Chart
**Collection:** `weather_observation`
**X-axis:** `observation_date`
**Y-axes:** `temperature_c`, `precipitation_mm`
**Filters:** Last 30 days

### 6. Financial Summary (Stats)

**Type:** Stats
**Collection:** `noi_snapshot`
**Filters:** Latest period for location
**Fields:** `net_revenue`, `noi`, `operating_margin_pct`

### 7. Remote Sensing (Line Chart)

**Type:** Line Chart
**Collection:** `remote_sensing_observation`
**X-axis:** `observation_date`
**Y-axis:** `ndvi`
**Filters:** Last 6 months

### 8. Alerts & Notifications (List)

**Type:** List
**Collection:** `sensor_alert`
**Filters:**
- `location_id` = assigned location
- `status` IN (`open`, `acknowledged`)

## Data Access Rules

```json
{
  "*": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "farm_activity": {
    "create": true,
    "update": "created_by = $CURRENT_USER.id"
  },
  "field_note": {
    "create": true,
    "update": "created_by = $CURRENT_USER.id"
  }
}
```

## Notes

- Operators have full CRUD on operational data
- Sensor data refreshes via cron job
- Alerts trigger Directus webhooks for real-time notifications
