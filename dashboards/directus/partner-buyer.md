# Partner Dashboard — Buyer View

## Overview

This dashboard provides buyers with visibility into farm production,
quality metrics, and delivery schedules. Designed for Directus.

## Setup

1. In Directus Admin → Settings → Roles → Create "Buyer" role
2. Grant read access to: `harvest_event`, `sales_event`, `partner`, `location`, `plot`, `crop_cycle`
3. Set up user accounts for buyer contacts in `partner.contact_email`
4. Create a Directus Dashboard with the modules below

## Modules

### 1. Production Summary (Stats Widget)

**Type:** Stats
**Collection:** `harvest_event`
**Filters:**
- `location_id` = current user's assigned location
- `status` IN (`approved`, `published`)

**Fields:**
- Sum of `quantity` (total harvest)
- Count of records
- Average `quality_grade` distribution

### 2. Upcoming Harvests (Table)

**Type:** Table
**Collection:** `crop_cycle`
**Filters:**
- `expected_harvest_date` >= TODAY
- `status` = `active`
- `location_id` = assigned location

**Columns:** `cycle_name`, `crop_id.name`, `expected_harvest_date`, `expected_yield`, `area_planted`

### 3. Recent Sales (Table)

**Type:** Table
**Collection:** `sales_event`
**Filters:**
- `partner_id` = current partner
- Last 90 days

**Columns:** `sale_date`, `crop_cycle_id.name`, `quantity`, `total_amount`, `payment_status`

### 4. Quality Grades (Donut Chart)

**Type:** Donut
**Collection:** `harvest_event`
**Group by:** `quality_grade`
**Filters:**
- `location_id` = assigned location
- Last 6 months

### 5. Revenue Trend (Line Chart)

**Type:** Line Chart
**Collection:** `sales_event`
**X-axis:** `sale_date` (monthly)
**Y-axis:** Sum of `total_amount`
**Filters:**
- `partner_id` = current partner
- Last 12 months

## Data Access Rules

```json
{
  "sales_event": {
    "read": "partner_id = $CURRENT_USER.partner_id",
    "fields": ["sale_date", "quantity", "unit", "total_amount", "payment_status", "crop_cycle_id"]
  },
  "harvest_event": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "fields": ["harvest_date", "quantity", "unit", "quality_grade", "crop_cycle_id"]
  }
}
```

## Notes

- Buyers see only their own transactions
- Quality grades are visible to encourage premium pricing
- Revenue trends help buyers plan procurement
