# Partner Dashboard — Vendor View

## Overview

This dashboard provides input vendors with visibility into
procurement needs, payment history, and demand forecasts.

## Setup

1. In Directus Admin → Settings → Roles → Create "Vendor" role
2. Grant read access to: `expense_event`, `partner`, `farm_activity`
3. Filter by vendor's partner_id

## Modules

### 1. Purchase Summary (Stats Widget)

**Type:** Stats
**Collection:** `expense_event`
**Filters:**
- `vendor_id` = current partner
- Last 12 months

**Fields:**
- Sum of `amount` (total purchases)
- Count of transactions
- Average order value

### 2. Purchase History (Table)

**Type:** Table
**Collection:** `expense_event`
**Filters:**
- `vendor_id` = current partner
- Last 6 months

**Columns:** `expense_date`, `category`, `description`, `amount`, `status`

### 3. Upcoming Demand (Forecast)

**Type:** Table
**Collection:** `forecast_output`
**Filters:**
- `metric_name` = `projected_revenue_usd`
- `location_id` = assigned location

**Purpose:** Vendors can anticipate demand based on farm projections

### 4. Payment Status (Donut Chart)

**Type:** Donut
**Collection:** `expense_event`
**Group by:** `status`
**Filters:**
- `vendor_id` = current partner

### 5. Category Breakdown (Pie Chart)

**Type:** Pie
**Collection:** `expense_event`
**Group by:** `category`
**Filters:**
- `vendor_id` = current partner
- Last 12 months

## Data Access Rules

```json
{
  "expense_event": {
    "read": "vendor_id = $CURRENT_USER.partner_id",
    "fields": ["expense_date", "category", "description", "amount", "status", "crop_cycle_id"]
  }
}
```

## Notes

- Vendors only see their own transactions
- Forecast visibility helps vendors prepare inventory
- Payment status tracking improves vendor relationships
