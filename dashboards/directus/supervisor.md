# Supervisor Dashboard

## Overview

Dashboard for field supervisors to manage team activities, approve submitted records, monitor harvest quality, and respond to sensor alerts.

## Setup

1. In Directus Admin → Settings → Roles → Use existing "Supervisor" role (`a1000000-0000-0000-0000-000000000002`)
2. Verify permissions in `config/directus/permissions.sql`
3. Assign `assigned_locations` for location-scoped access

## Modules

### 1. Team Activity (Stats Row)

**Type:** Stats  
**Collection:** `farm_activity`  
**Filters:**
- `location_id` = assigned location
- Last 7 days

**Metrics:**
- Count of activities
- Sum of `labor_hours`
- Distinct count of `created_by` (active workers)

### 2. Pending Approvals (Table)

**Type:** Table  
**Collection:** `approval`  
**Filters:**
- `location_id` = assigned location
- `status` = `pending`

**Columns:** `entity_type`, `entity_id`, `requested_by`, `requested_at`, `approval_type`  
**Sort:** `requested_at` ASC

### 3. Submitted Records (Table)

**Type:** Table  
**Collection:** `farm_activity`  
**Filters:**
- `location_id` = assigned location
- `status` = `submitted`

**Columns:** `activity_type`, `created_by`, `activity_date`, `plot_id.name`, `status`

### 4. Harvest Quality (Table)

**Type:** Table  
**Collection:** `harvest_event`  
**Filters:**
- `location_id` = assigned location
- Last 30 days
- `status` IN (`submitted`, `verified`)

**Columns:** `harvest_date`, `crop_cycle_id.name`, `quantity`, `quality_grade`, `status`

### 5. Sensor Alerts (Table)

**Type:** Table  
**Collection:** `sensor_alert`  
**Filters:**
- `location_id` = assigned location
- `status` IN (`open`, `acknowledged`)

**Columns:** `severity`, `message`, `reading_value`, `triggered_at`

## Data Access Rules

```json
{
  "farm_activity": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "update": true
  },
  "approval": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "create": true,
    "update": true
  },
  "harvest_event": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "update": true
  }
}
```

## Notes

- Supervisors can submit and approve operational records
- Cannot verify or publish (requires Manager/Finance role)
- Approval actions logged to `workflow_history`
