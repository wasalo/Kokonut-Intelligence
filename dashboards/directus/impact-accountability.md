# Impact & Accountability Dashboard

## Overview

Impact claim tracking, evidence maturity assessment, attestation coverage, and metric proposals.

## Setup

1. In Directus Admin → Settings → Roles → Assign to Manager, Analyst, or Auditor roles
2. Create/read access for impact claims and proposals
3. Location-scoped via `assigned_locations`

## Modules

### 1. Impact Summary (Stats Row)

**Type:** Stats  
**Collection:** `impact_claim`

**Metrics:**
- Total claims
- Published count
- Pending count

### 2. Impact Claims (Table)

**Type:** Table  
**Collection:** `impact_claim`

**Columns:** `claim_type`, `claim_text`, `evidence_maturity`, `framework_alignment`, `status`

### 3. Attestation Coverage (Table)

**Type:** Table  
**Collection:** `attestation_record`  
**Filters:** Subject type = location

**Columns:** `attested_at`, `claim_data`, `attestation_uid`, `chain`, `status`

### 4. Metric Proposals (Table)

**Type:** Table  
**Collection:** `metric_proposal`

**Columns:** `proposal_date`, `metric_name`, `proposed_by`, `discussion_count`, `status`

### 5. MRV Claims (Table)

**Type:** Table  
**Collection:** `mrv_claim`

**Columns:** `created_at`, `claim_type`, `subject_type`, `status`

## Data Access Rules

```json
{
  "impact_claim": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "create": true
  },
  "attestation_record": {
    "read": "subject_id IN ($CURRENT_USER.assigned_locations)"
  },
  "metric_proposal": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "create": true
  }
}
```

## Notes

- Impact claims require evidence maturity >= 4 for public visibility
- Public carbon claims require maturity 6 and third-party verification
- Metric proposals require 30-day discussion period
