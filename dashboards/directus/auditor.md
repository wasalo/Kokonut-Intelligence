# Auditor Dashboard

## Overview

Compliance audit dashboard for reviewing audit logs, workflow transitions, attestation records, agent activity, and report snapshots.

## Setup

1. In Directus Admin → Settings → Roles → Use existing "Auditor" role (`a1000000-0000-0000-0000-000000000009`)
2. Verify permissions in `config/directus/permissions.sql`
3. Read-only access to all statuses (including draft)

## Modules

### 1. Audit Log (Table)

**Type:** Table  
**Collection:** `audit_log`  
**Filters:** Last 30 days

**Columns:** `timestamp`, `actor`, `action`, `collection`, `record_id`, `ip_address`  
**Sort:** `timestamp` DESC

### 2. Workflow Transitions (Table)

**Type:** Table  
**Collection:** `workflow_history`  
**Filters:** Last 30 days

**Columns:** `changed_at`, `entity_type`, `entity_id`, `from_status`, `to_status`, `changed_by`

### 3. Attestation Records (Table)

**Type:** Table  
**Collection:** `attestation_record`  
**Filters:** Last 90 days

**Columns:** `attested_at`, `subject_type`, `subject_id`, `attestation_uid`, `chain`, `status`

### 4. Agent Activity (Table)

**Type:** Table  
**Collection:** `agent_action_log`  
**Filters:** Last 7 days

**Columns:** `created_at`, `agent_id.name`, `action_type`, `entity_type`, `status`

### 5. Report Snapshots (Table)

**Type:** Table  
**Collection:** `report_snapshot`  
**Filters:** Last 30 days

**Columns:** `report_type`, `location_id.name`, `generated_at`, `status`, `public_interest_summary`

### 6. MRV Claims (Table)

**Type:** Table  
**Collection:** `mrv_claim`  
**Filters:** Last 90 days

**Columns:** `created_at`, `claim_type`, `subject_type`, `subject_id`, `status`

## Data Access Rules

```json
{
  "*": {
    "read": true
  }
}
```

## Notes

- Auditors have read-only access to all data regardless of status
- Can view draft, submitted, verified, and published records
- Full audit trail available for compliance reviews
