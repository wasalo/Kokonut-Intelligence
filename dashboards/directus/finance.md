# Finance Dashboard

## Overview

Financial operations dashboard for expense approval, revenue tracking, NOI analysis, cost allocation, and budget monitoring.

## Setup

1. In Directus Admin → Settings → Roles → Use existing "Finance" role (`a1000000-0000-0000-0000-000000000004`)
2. Verify permissions in `config/directus/permissions.sql`
3. Assign `assigned_locations` for location-scoped access

## Modules

### 1. Financial Overview (Stats Row)

**Type:** Stats  
**Collection:** `noi_snapshot`  
**Filters:** `location_id` = assigned location

**Metrics:**
- Sum of `net_revenue`
- Sum of `total_costs`
- Sum of `noi`
- Average `operating_margin_pct`

### 2. Pending Expense Approval (Table)

**Type:** Table  
**Collection:** `expense_event`  
**Filters:**
- `location_id` = assigned location
- `status` = `submitted`

**Columns:** `expense_date`, `category`, `amount`, `vendor`, `created_by`, `status`

### 3. Revenue by Crop (Bar)

**Type:** Bar  
**Collection:** `sales_event`  
**X-axis:** `crop_cycle_id.name`  
**Y-axis:** Sum of `total_amount`  
**Filters:** Last 90 days, verified/published

### 4. NOI Trend (Line)

**Type:** Line  
**Collection:** `noi_snapshot`  
**X-axis:** `period_end` (monthly)  
**Y-axes:**
- `net_revenue` (green)
- `total_costs` (red)
- `noi` (blue)

### 5. CapEx Breakdown (Table)

**Type:** Table  
**Collection:** `capex_breakdown`  
**Filters:** `location_id` = assigned location

**Columns:** `category`, `amount`, `depreciation_method`, `useful_life_years`

### 6. Verified Expenses (Table)

**Type:** Table  
**Collection:** `expense_event`  
**Filters:** Last 30 days, verified/published

**Columns:** `expense_date`, `category`, `amount`, `vendor`, `status`

## Data Access Rules

```json
{
  "noi_snapshot": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "expense_event": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "update": true
  },
  "sales_event": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "capex_breakdown": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  }
}
```

## Notes

- Finance can verify expenses and sales
- Cannot publish (requires Admin role)
- NOI calculated by `metrics-calculator.ts` hook
