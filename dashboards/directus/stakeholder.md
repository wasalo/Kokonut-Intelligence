# Stakeholder Governance Dashboard

## Overview

Stakeholder feedback collection, outcome tracking, engagement monitoring, and grievance management.

## Setup

1. In Directus Admin → Settings → Roles → Assign to Manager, Supervisor, or Auditor roles
2. Create/read access for feedback submission
3. Location-scoped via `assigned_locations`

## Modules

### 1. Feedback Summary (Stats Row)

**Type:** Stats  
**Collection:** `stakeholder_feedback`

**Metrics:**
- Total feedback count
- Pending review count
- Published count

### 2. Recent Feedback (Table)

**Type:** Table  
**Collection:** `stakeholder_feedback`  
**Filters:** Last 30 days

**Columns:** `submitted_at`, `feedback_type`, `group_name`, `sentiment`, `consent_given`, `status`

### 3. Stakeholder Outcomes (Table)

**Type:** Table  
**Collection:** `stakeholder_outcome`

**Columns:** `outcome_date`, `outcome_type`, `description`, `evidence_maturity`, `status`

### 4. Pending Reviews (Table)

**Type:** Table  
**Collection:** `stakeholder_feedback_review`  
**Filters:** `status` = `pending`

**Columns:** `feedback_id.feedback_type`, `feedback_id.group_name`, `reviewer_id`, `submitted_at`

### 5. Grievance Cases (Table)

**Type:** Table  
**Collection:** `stakeholder_grievance_case`

**Columns:** `case_number`, `grievance_type`, `severity`, `status`, `filed_at`

## Data Access Rules

```json
{
  "stakeholder_feedback": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "create": true
  },
  "stakeholder_outcome": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)"
  },
  "stakeholder_feedback_review": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "create": true
  }
}
```

## Notes

- Feedback requires 7-day review period before verification
- Consent required for public summary publication
- Grievance cases tracked through resolution
