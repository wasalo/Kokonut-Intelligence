# Governance Cockpit Dashboard

## Overview

DAO governance oversight: proposals, guild activity, governance circles, tensions, and coordination.

## Setup

1. In Directus Admin → Settings → Roles → Assign to Manager or Auditor roles
2. Read-only access to governance collections
3. Network-wide view (not location-scoped)

## Modules

### 1. Governance Summary (Stats Row)

**Type:** Stats  
**Collection:** `dao_proposal`

**Metrics:**
- Total proposals
- Active count
- Passed count

### 2. DAO Proposals (Table)

**Type:** Table  
**Collection:** `dao_proposal`

**Columns:** `proposal_id`, `title`, `proposer`, `created_at`, `votes_for`, `votes_against`, `status`

### 3. Guild Activity (Table)

**Type:** Table  
**Collection:** `guild_contribution`

**Columns:** `guild_id.name`, `contributor_id`, `contribution_type`, `hours`, `contributed_at`

### 4. Governance Circles (Table)

**Type:** Table  
**Collection:** `governance_circle`

**Columns:** `circle_name`, `purpose`, `member_count`, `status`

### 5. Open Tensions (Table)

**Type:** Table  
**Collection:** `governance_tension`  
**Filters:** `status` IN (`open`, `active`)

**Columns:** `tension_title`, `raised_by`, `category`, `severity`, `raised_at`

## Data Access Rules

```json
{
  "*": {
    "read": true
  }
}
```

## Notes

- Network-wide governance view
- DAO proposals from Gnosis Chain indexing
- Guild data from Colony integration
- Tensions from governance circles
