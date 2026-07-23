# Bio-Factory Operations Dashboard

## Overview

Bio-input production management: batches, recipes, quality tests, provenance tracking, and regional inputs.

## Setup

1. In Directus Admin → Settings → Roles → Assign to Manager or Field Worker roles
2. Create/read access for bio-factory collections
3. Location-scoped via `assigned_locations`

## Modules

### 1. Production Summary (Stats Row)

**Type:** Stats  
**Collection:** `bio_factory_batch`

**Metrics:**
- Total batches
- Active count
- Total produced quantity

### 2. Recent Batches (Table)

**Type:** Table  
**Collection:** `bio_factory_batch`

**Columns:** `batch_number`, `recipe_id.name`, `production_date`, `quantity_produced`, `quality_score`, `status`

### 3. Recipe Library (Table)

**Type:** Table  
**Collection:** `bio_recipe_library`  
**Filters:** `status` = `active`

**Columns:** `recipe_name`, `category`, `target_pest`, `efficacy_rating`, `cost_per_unit`

### 4. Quality Tests (Table)

**Type:** Table  
**Collection:** `bio_quality_test`

**Columns:** `test_date`, `batch_id.batch_number`, `test_type`, `result`, `passed`

### 5. Input Provenance (Table)

**Type:** Table  
**Collection:** `bio_input_provenance`

**Columns:** `input_name`, `source_type`, `origin_location`, `certification`, `traceability_id`

## Data Access Rules

```json
{
  "bio_factory_batch": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "create": true
  },
  "bio_recipe_library": {
    "read": true
  },
  "bio_quality_test": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "create": true
  },
  "bio_input_provenance": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  }
}
```

## Notes

- Recipes are shared across all locations
- Quality tests linked to batches
- Provenance tracking for organic certification
