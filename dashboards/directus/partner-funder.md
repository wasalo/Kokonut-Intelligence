# Partner Dashboard — Funder View

## Overview

This dashboard provides funders/investors with visibility into
financial performance, ecological outcomes, and impact metrics.

## Setup

1. In Directus Admin → Settings → Roles → Create "Funder" role
2. Grant read access to: `noi_snapshot`, `forecast_output`, `forecast_scenario`,
   `attestation_record`, `treasury_event`, `location`, `farm`
3. Create API tokens for automated reporting

## Modules

### 1. Financial Performance (Stats Widget)

**Type:** Stats
**Collection:** `noi_snapshot`
**Filters:**
- `location_id` = assigned location
- Latest period

**Fields:**
- Sum of `net_revenue`
- Sum of `noi`
- Average `operating_margin_pct`

### 2. NOI Trend (Line Chart)

**Type:** Line Chart
**Collection:** `noi_snapshot`
**X-axis:** `period_end` (quarterly)
**Y-axis:** Sum of `noi`
**Filters:** `location_id` = assigned location

### 3. Cost Breakdown (Bar Chart)

**Type:** Bar Chart
**Collection:** `expense_event`
**Group by:** `category`
**Y-axis:** Sum of `amount`
**Filters:** Last 12 months

### 4. Forecast Comparison (Table)

**Type:** Table
**Collection:** `forecast_output`
**Filters:**
- `metric_name` IN (`projected_noi_usd`, `operating_margin_pct`)
- `location_id` = assigned location

**Columns:** `metric_name`, `value`, `unit`, `confidence_low`, `confidence_high`

### 5. Impact Attestations (List)

**Type:** List
**Collection:** `attestation_record`
**Filters:**
- `claim_type` IN (`impact`, `mrv`)
- `status` = `attested`

**Fields:** `claim_data`, `attested_at`, `chain`

### 6. Ecological Outcomes (Stats)

**Type:** Stats
**Collection:** `remote_sensing_observation`
**Filters:** `location_id` = assigned location

**Fields:**
- Average `ndvi` (trend arrow)
- Average `canopy_cover_pct`

## Data Access Rules

```json
{
  "noi_snapshot": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "forecast_output": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "expense_event": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "fields": ["category", "amount", "expense_date"]
  }
}
```

## Notes

- Funders see aggregated financial data only
- No individual buyer or vendor information exposed
- Ecological metrics build confidence in regenerative claims
- Attestations provide on-chain verification
