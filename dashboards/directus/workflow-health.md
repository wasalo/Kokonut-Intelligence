# Workflow Health Dashboard

## Overview

Operational workflow monitoring: transitions, pending approvals, status distribution, and pipeline health.

## Setup

1. In Directus Admin → Settings → Roles → Assign to Manager, Supervisor, or Auditor roles
2. Read-only access to workflow collections
3. Supervisor+ can approve pending items

## Modules

### 1. Transition Summary (Stats Row)

**Type:** Stats  
**Collection:** `workflow_history`  
**Filters:** Last 7 days

**Metrics:**
- Total transitions
- Rejected count

### 2. Recent Transitions (Table)

**Type:** Table  
**Collection:** `workflow_history`  
**Filters:** Last 7 days

**Columns:** `changed_at`, `entity_type`, `entity_id`, `from_status`, `to_status`, `changed_by`

### 3. Pending Approvals (Table)

**Type:** Table  
**Collection:** `approval`  
**Filters:** `status` = `pending`

**Columns:** `entity_type`, `entity_id`, `requested_by`, `requested_at`, `approval_type`

### 4. Submitted Records (Stats)

**Type:** Stats  
**Collection:** `farm_activity`  
**Filters:** `status` = `submitted`

**Metrics:** Count of submitted activities

### 5. Rejected Records (Table)

**Type:** Table  
**Collection:** `workflow_history`  
**Filters:** `to_status` = `rejected`, last 30 days

**Columns:** `changed_at`, `entity_type`, `entity_id`, `changed_by`

## Data Access Rules

```json
{
  "workflow_history": {
    "read": true
  },
  "approval": {
    "read": true,
    "create": true,
    "update": true
  }
}
```

## Notes

- Workflow state machine defined in `workflow.ts`
- 53 collections governed by lifecycle
- Role-based approval routing per collection/status
