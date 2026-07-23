# Agent Activity Dashboard

## Overview

AI agent oversight: task tracking, summaries, action logs, and safety monitoring.

## Setup

1. In Directus Admin → Settings → Roles → Assign to Analyst, Manager, or Auditor roles
2. Read-only access to agent collections
3. Agent Write/Full roles can create summaries

## Modules

### 1. Agent Summary (Stats Row)

**Type:** Stats  
**Collection:** `agent_task`  
**Filters:** Last 7 days

**Metrics:**
- Total tasks
- Completed count
- Failed count

### 2. Recent Tasks (Table)

**Type:** Table  
**Collection:** `agent_task`  
**Filters:** Last 7 days

**Columns:** `created_at`, `agent_id.name`, `task_type`, `entity_type`, `status`

### 3. AI Summaries (Table)

**Type:** Table  
**Collection:** `ai_summary`  
**Filters:** Last 30 days, assigned location

**Columns:** `created_at`, `summary_type`, `location_id.name`, `status`

### 4. Action Log (Table)

**Type:** Table  
**Collection:** `agent_action_log`  
**Filters:** Last 7 days

**Columns:** `created_at`, `agent_id.name`, `action_type`, `entity_type`, `entity_id`, `status`

### 5. Registered Agents (Table)

**Type:** Table  
**Collection:** `agent_identity`

**Columns:** `name`, `agent_type`, `status`, `last_active_at`

## Data Access Rules

```json
{
  "agent_task": {
    "read": true
  },
  "ai_summary": {
    "read": "location_id IN ($CURRENT_USER.assigned_locations)",
    "create": true
  },
  "agent_action_log": {
    "read": true
  },
  "agent_identity": {
    "read": true
  }
}
```

## Notes

- High-risk agent actions require human approval
- Agent safety enforced via `agent-safety.ts` hook
- Action log provides full audit trail
