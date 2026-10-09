# Field Worker Dashboard

## Overview

Daily-use dashboard for field staff to manage tasks, log activities, record harvests, and submit field notes. Optimized for mobile data entry.

## Setup

1. In Directus Admin → Settings → Roles → Use existing "Field Worker" role (`a1000000-0000-0000-0000-000000000001`)
2. Verify permissions in `config/directus/permissions.sql`
3. Assign `assigned_locations` to user for location-scoped access

## Modules

### 1. Today's Tasks (Table)

**Type:** Table  
**Collection:** `farm_activity`  
**Filters:**
- `location_id` = assigned location
- `activity_date` = today
- `status` IN (`draft`, `submitted`)

**Columns:** `activity_type`, `plot_id.name`, `planned_start`, `planned_end`, `status`  
**Sort:** `planned_start` ASC

### 2. Quick Stats (Stats Row)

**Type:** Stats  
**Collection:** `farm_activity`  
**Filters:**
- `created_by` = current user
- Last 7 days

**Metrics:**
- Count of activities
- Sum of `labor_hours`

### 3. Recent Harvests (Table)

**Type:** Table  
**Collection:** `harvest_event`  
**Filters:**
- `created_by` = current user
- Last 7 days

**Columns:** `harvest_date`, `crop_cycle_id.name`, `quantity`, `unit`, `quality_grade`

### 4. Sensor Readings (Table)

**Type:** Table  
**Collection:** `sensor_reading`  
**Filters:**
- `location_id` = assigned location
- Last 24 hours

**Columns:** `sensor_type`, `value`, `unit`, `reading_date`

### 5. My Field Notes (Table)

**Type:** Table  
**Collection:** `field_note`  
**Filters:**
- `created_by` = current user
- Last 7 days

**Columns:** `note_date`, `note_type`, `title`, `status`

## Data Access Rules

```json
{
  "farm_activity": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "create": true,
    "update": "created_by = $CURRENT_USER.id"
  },
  "harvest_event": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "create": true,
    "update": "created_by = $CURRENT_USER.id"
  },
  "field_note": {
    "read": "created_by = $CURRENT_USER.id",
    "create": true,
    "update": "created_by = $CURRENT_USER.id"
  }
}
```

## Notes

- Field workers can create records but cannot verify or publish
- All records start in `draft` status
- Location scope enforced via `assigned_locations`
