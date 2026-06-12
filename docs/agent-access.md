# Agent & MCP Access Guide

Kokonut Intelligence supports AI agent access through Directus native MCP (Model Context Protocol) support. Agents interact with the same governed objects as humans, under the same permission model.

Agent identity, payment, escrow, and reputation logic are not implemented in this repository. Those marketplace concerns remain external and are attributed to `Kokonut-Agentic-Marketplace`. This repository stores metadata, capability manifests, task records, action logs, and governed data access patterns.

## Agent Metadata Collections

| Collection | Purpose |
|------------|---------|
| `agent_identity` | Agent name, operator wallet metadata, manifest CID, marketplace source, and `agent_state` |
| `agent_capability_manifest` | Versioned JSON manifest with inputs, outputs, pricing metadata, CID, and hash |
| `agent_task` | Task inputs, outputs, output CID/hash, execution state, human review lifecycle, and optional attestation request link |
| `agent_action_log` | Collection/action audit trail with payload hash and `action_result` |

```bash
# Print a local capability manifest example
python3 -m services.agents --example kokonut-mrv-reporter

# Validate and pin a manifest to the local CID adapter
python3 -m services.agents --validate manifest.json --pin-local
```

## Directus Native MCP Support

Directus exposes an MCP-compatible interface that allows AI agents to read and write data using the same REST/GraphQL API that humans use. Agents authenticate with scoped tokens and are subject to role-based permissions.

### Connecting an Agent

```python
import os
from directus_sdk import DirectusClient

client = DirectusClient(
    url=os.environ["DIRECTUS_URL"],
    token=os.environ["AGENT_TOKEN"],  # Scoped static token
)
```

## Agent-Scoped Tokens

Each agent receives a token with explicit permissions. Three levels are supported:

| Scope | Permissions | Use Case |
|-------|------------|----------|
| `read-only` | Read access to verified or published collections | Data analysis, reporting agents |
| `write-draft` | Read + create/update with `status=draft` | Data entry agents, AI summarizers |
| `full-access` | Read + write to governed collections | Automated workflow agents |

### Creating an Agent Token

```bash
# Create an agent role
curl -X POST http://localhost:8055/roles \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "agent-harvest-reader",
    "description": "Read-only agent for harvest data analysis",
    "admin_access": false,
    "app_access": false
  }'

# Create user for the agent
curl -X POST http://localhost:8055/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "agent-harvest@kokonut.network",
    "password": "agent-generated-password",
    "role": "AGENT_ROLE_ID",
    "app_metadata": {
      "agent_type": "harvest_analyzer",
      "allowed_collections": ["harvest_event", "crop_cycle", "plot"]
    }
  }'

# Generate static token via Directus admin
```

## Permission Boundaries Per Agent Type

| Agent Type | Collections | Actions | Restrictions |
|-----------|------------|---------|-------------|
| Harvest Analyzer | `harvest_event`, `crop_cycle`, `plot` | Read | Only `verified` status |
| Expense Tracker | `expense_event`, `expense_category` | Read | Only `verified` or `published` status |
| AI Summarizer | `harvest_event`, `farm_activity`, `field_note` | Read + Write draft | Can create `ai_summary` |
| Attestation Agent | `attestation_record`, `attestation_schema` | Read + Write draft | Cannot submit on-chain |
| MRV Reporter | `farm_registry_record`, `mrv_event`, `attestation_request`, `agent_task` | Read verified + write draft/submitted metadata | Cannot sign EAS transactions |
| Compliance Agent | `audit_log`, `workflow_history` | Read | All records |

### Permission Configuration

Permissions are set via Directus role policies. Example for a read-only harvest agent:

```sql
-- Agent can only read verified harvest events
INSERT INTO directus_permissions (role, collection, action, permissions, fields)
VALUES (
    (SELECT id FROM directus_role WHERE name = 'agent-harvest-reader'),
    'harvest_event',
    'read',
    '{"status": {"_eq": "verified"}}',
    '*'
);

-- Agent cannot read expense data
INSERT INTO directus_permissions (role, collection, action, permissions, fields)
VALUES (
    (SELECT id FROM directus_role WHERE name = 'agent-harvest-reader'),
    'expense_event',
    'read',
    'false',
    '*'
);
```

## Workflow: Agent-Driven Data Pipeline

```
Agent reads verified data → Creates draft summary → Requests human review → Published
```

### Step-by-Step

1. **Agent reads verified data** — Queries `harvest_event` where `status = 'verified'`
2. **Agent creates draft summary** — Writes to `ai_summary` with `status = 'draft'`
3. **Agent requests review** — Creates a `workflow_history` entry or `approval` record
4. **Human reviews** — Approves or rejects via Directus UI or API
5. **Summary published** — Status changes to `published`, available to dashboards

### Example: Agent Creates an AI Summary

```python
# Agent reads verified harvests
harvests = client.request(
    read_items("harvest_event", {
        "filter": {"status": {"_eq": "verified"}},
        "fields": ["harvest_date", "quantity", "unit", "quality_grade", "crop_cycle_id.name"],
    })
)

# Agent generates summary
summary = f"Summary of {len(harvests)} verified harvest events..."

# Agent writes draft summary
result = client.request(
    create_items("ai_summary", {
        "subject_type": "location",
        "subject_id": LOCATION_ID,
        "summary_type": "operations",
        "content": summary,
        "status": "draft",  # Cannot publish directly
        "source_tables": ["harvest_event"],
        "model_version": "gpt-4o",
        "confidence": 0.87,
    })
)

# Agent logs the action
client.request(
    create_items("workflow_history", {
        "collection": "ai_summary",
        "record_id": result["id"],
        "to_status": "draft",
        "notes": "AI-generated harvest summary. Pending human review.",
    })
)
```

## Audit Logging

All agent actions are tracked in `workflow_history`:

```sql
-- View all agent actions
SELECT
    wh.collection,
    wh.record_id,
    wh.from_status,
    wh.to_status,
    wh.changed_at,
    wh.notes
FROM workflow_history wh
WHERE wh.notes LIKE '%AI-generated%'
ORDER BY wh.changed_at DESC;
```

The `audit_log` table also captures all API mutations with user context:

```sql
-- Agent audit trail
SELECT al.timestamp, al.user_email, al.action, al.collection, al.record_id, al.new_data
FROM audit_log al
WHERE al.user_email LIKE '%agent%'
ORDER BY al.timestamp DESC;
```

## Security: Approval Gates

Agents **cannot bypass approval gates**. The following constraints are enforced at the database level:

1. **Status transitions are controlled** — Agents can only set `status = 'draft'`
2. **Publishing requires human approval** — Directus permissions restrict `status = 'published'` to human roles
3. **On-chain attestation requires signature** — Only authorized wallets or configured external signer services can submit to EAS
4. **All mutations are logged** — Even if an agent tries to escalate, the audit trail records it
5. **Marketplace logic is external** — x402/ERC-8004 payment, escrow, and reputation workflows are not handled by this repository

### Enforcement via Directus Policies

```sql
-- Agent role CANNOT set status to 'published'
INSERT INTO directus_permissions (role, collection, action, permissions, fields)
VALUES (
    (SELECT id FROM directus_role WHERE name = 'agent-harvest-reader'),
    'ai_summary',
    'update',
    '{"status": {"_eq": "draft"}}',  -- Can only update draft records
    'content,confidence,source_record_ids'
);

-- Agent role CANNOT create records with status other than draft
INSERT INTO directus_permissions (role, collection, action, permissions, fields)
VALUES (
    (SELECT id FROM directus_role WHERE name = 'agent-harvest-reader'),
    'ai_summary',
    'create',
    'true',
    'subject_type,subject_id,summary_type,content,source_tables,model_version,confidence'
);
```

## Troubleshooting

### Agent gets 403 Forbidden

The agent token lacks permission for the requested collection/action. Check the agent's role permissions in Directus admin.

### Agent creates records with unexpected status

Verify the Directus permission `filters` restrict status transitions. Agents should only be able to create records with `status = 'draft'`.

### Audit log shows no agent activity

Ensure the agent is using its own static token, not the admin token. Agent tokens are linked to agent users in `directus_user`.
