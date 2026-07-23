# Carbon Credits Dashboard

## Overview

Carbon credit lifecycle tracking: issuance, adjustments, retirements, certificates, and MRV claims.

## Setup

1. In Directus Admin → Settings → Roles → Assign to Manager, Finance, or Auditor roles
2. Read-only access to carbon credit collections
3. Location-scoped via `assigned_locations`

## Modules

### 1. Credit Summary (Stats Row)

**Type:** Stats  
**Collection:** `carbon_credit`  
**Filters:** `location_id` = assigned location

**Metrics:**
- Sum of `quantity`
- Count of credit records

### 2. Credit Inventory (Table)

**Type:** Table  
**Collection:** `carbon_credit`  
**Filters:** Active/partially retired credits

**Columns:** `credit_class_id.name`, `vintage_year`, `quantity`, `retired_quantity`, `methodology`, `status`

### 3. Retirement Records (Table)

**Type:** Table  
**Collection:** `credit_retirement`

**Columns:** `retirement_date`, `quantity`, `retirement_reason`, `beneficiary`, `status`

### 4. Retirement Certificates (Table)

**Type:** Table  
**Collection:** `retirement_certificate`

**Columns:** `certificate_number`, `retirement_id.quantity`, `issued_at`, `hash`

### 5. MRV Claims (Table)

**Type:** Table  
**Collection:** `mrv_claim`  
**Filters:** `claim_type` = `carbon`

**Columns:** `created_at`, `claim_type`, `subject_type`, `status`

## Data Access Rules

```json
{
  "carbon_credit": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "credit_retirement": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "retirement_certificate": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  }
}
```

## Notes

- Carbon credits linked to credit classes and methodologies
- Retirement certificates include SHA-256 hash for verification
- MRV claims track monitoring, reporting, and verification status
