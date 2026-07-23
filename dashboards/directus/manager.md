# Manager Dashboard

## Overview

Comprehensive farm management dashboard covering crop cycles, financial performance, team productivity, expenses, and sales.

## Setup

1. In Directus Admin → Settings → Roles → Use existing "Manager" role (`a1000000-0000-0000-0000-000000000003`)
2. Verify permissions in `config/directus/permissions.sql`
3. Assign `assigned_locations` for location-scoped access

## Modules

### 1. Farm Overview (Stats Row)

**Type:** Stats  
**Collection:** `crop_cycle`  
**Filters:** `location_id` = assigned location

**Metrics:**
- Count of active cycles
- Sum of `yield_target`

### 2. Financial Summary (Stats Row)

**Type:** Stats  
**Collection:** `noi_snapshot`  
**Filters:** `location_id` = assigned location

**Metrics:**
- Sum of `net_revenue`
- Sum of `noi`
- Average `operating_margin_pct`

### 3. Crop Cycle Status (Table)

**Type:** Table  
**Collection:** `crop_cycle`  
**Filters:**
- `location_id` = assigned location
- `status` IN (`planted`, `growing`, `harvested`)

**Columns:** `cycle_name`, `crop_id.name`, `planting_date`, `expected_harvest_date`, `yield_target`, `status`

### 4. Expense Breakdown (Pie)

**Type:** Pie  
**Collection:** `expense_event`  
**Group by:** `category`  
**Value:** Sum of `amount`  
**Filters:** Last 90 days, verified/published

### 5. Team Productivity (Table)

**Type:** Table  
**Collection:** `farm_activity`  
**Filters:** Last 30 days, assigned location  
**Group by:** `created_by`  
**Metrics:** Count of activities, sum of `labor_hours`

### 6. Recent Sales (Table)

**Type:** Table  
**Collection:** `sales_event`  
**Filters:** Last 30 days, assigned location

**Columns:** `sale_date`, `crop_cycle_id.name`, `quantity`, `total_amount`, `payment_status`

## Data Access Rules

```json
{
  "crop_cycle": {
    "read": "plot_id.farm_id.location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "noi_snapshot": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "expense_event": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "update": true
  },
  "sales_event": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "update": true
  }
}
```

## Notes

- Managers can approve operational records
- Cannot verify expenses (requires Finance role)
- Financial data aggregated from NOI snapshots
