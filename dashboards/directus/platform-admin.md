# Platform Admin Dashboard

## Overview

Platform health and operations: migration status, API keys, webhooks, scheduled jobs, and agent safety monitoring.

## Setup

1. In Directus Admin → Settings → Roles → Assign to Admin role only
2. Full read access to all system collections
3. Network-wide view (not location-scoped)

## Modules

### 1. System Overview (Stats Row)

**Type:** Stats  
**Collection:** `schema_migration`

**Metrics:**
- Total migrations applied

### 2. Migration History (Table)

**Type:** Table  
**Collection:** `schema_migration`

**Columns:** `filename`, `applied_at`, `checksum`, `execution_ms`  
**Sort:** `applied_at` DESC

### 3. API Keys (Table)

**Type:** Table  
**Collection:** `api_key`

**Columns:** `name`, `key_prefix`, `scopes`, `expires_at`, `last_used_at`, `status`

### 4. Webhooks (Table)

**Type:** Table  
**Collection:** `webhook`

**Columns:** `name`, `url`, `events`, `status`, `last_triggered_at`

### 5. Scheduled Jobs (Table)

**Type:** Table  
**Collection:** `scheduled_job`

**Columns:** `name`, `cron_expression`, `last_run_at`, `next_run_at`, `status`

### 6. Agent Safety Log (Table)

**Type:** Table  
**Collection:** `agent_action_log`  
**Filters:** `status` = `blocked`

**Columns:** `created_at`, `agent_id.name`, `action_type`, `entity_type`, `reason`

### 7. Recent Agent Activity (Table)

**Type:** Table  
**Collection:** `agent_action_log`  
**Filters:** Last 24 hours

**Columns:** `created_at`, `agent_id.name`, `action_type`, `entity_type`, `status`

## Data Access Rules

```json
{
  "*": {
    "read": true
  }
}
```

## Notes

- Admin-only dashboard
- API key values are never exposed (only prefix)
- Agent safety violations logged and surfaced
- Migration checksums enable drift detection
