# Agent & MCP Access Guide

Kokonut Intelligence supports AI agent access through the Directus REST API with role-based permission policies. Agents interact with the same governed objects as humans, under the same permission model — with additional safety enforcement layers that prevent agents from verifying, publishing, or modifying human-governed records.

Agent identity, payment, escrow, and reputation logic are not implemented in this repository. Those marketplace concerns remain external and are attributed to `Kokonut-Agentic-Marketplace`. This repository stores metadata, capability manifests, task records, action logs, and governed data access patterns.

Directus 12.1.1 includes native MCP (Model Context Protocol) support as a product feature. This repository does not implement a custom MCP server — agents connect via the Directus REST API or the platform's built-in MCP interface.

## Agent Metadata Collections

Four collections store agent state and audit trails (`schemas/postgres/013_prd_completion.sql`):

| Collection | Purpose | Key Columns |
|------------|---------|-------------|
| `agent_identity` | Agent registration and operator metadata | `agent_name` (UNIQUE), `operator_wallet`, `ens_subdomain`, `erc8004_agent_id`, `capability_manifest_cid`, `payment_token`, `base_rate_usdc`, `marketplace_source`, `agent_state` (active/paused/deregistered), `metadata` (JSONB) |
| `agent_capability_manifest` | Versioned capability manifest with CID pinning | `agent_id` (FK), `version`, `manifest` (JSONB), `manifest_cid`, `manifest_hash`, `is_active`; UNIQUE on `(agent_id, version)` |
| `agent_task` | Task execution lifecycle with human review | `agent_id` (FK), `task_type`, `subject_type`, `subject_id`, `inputs` (JSONB), `output` (JSONB), `output_cid`, `output_hash`, `payment_metadata` (JSONB), `execution_status` (queued/running/completed/failed/cancelled), `review_status` (draft/submitted/verified/published/rejected), `attestation_request_id` (FK) |
| `agent_action_log` | Collection/action audit trail with tamper evidence | `agent_id` (FK), `task_id` (FK), `action`, `collection`, `record_id`, `payload_hash` (SHA-256), `action_result` (success/failed/skipped), `error_message`, `metadata` (JSONB), `high_risk` (BOOLEAN), `requires_human_approval` (BOOLEAN) |

## Agent Roles

Three Directus roles are provisioned for agent access (`config/directus/permissions.sql:495-508`):

| Role | Slug | Description |
|------|------|-------------|
| `Agent Read-Only` | `agent_read_only` | Read-only access to verified/published data and agent metadata |
| `Agent Write` | `agent_write` | Can create draft records, submit for review, log actions |
| `Agent Full` | `agent_full` | Full read/write access with approval gates for high-risk operations |

Each role is linked to a Directus policy via `directus_access`. Role detection uses resolved role slugs (lowercase, underscored) — never raw UUIDs. The `isAgentActorByRoles()` function in `extensions/kokonut-hooks/src/agent-safety.ts:70-78` matches `agent_read_only`, `agent_write`, `agent_full`, or any slug starting with `agent`.

## Connecting an Agent

### Python SDK

The `kokonut-intelligence` package provides a typed client wrapping the Directus REST API:

```bash
pip install kokonut-intelligence
```

```python
from kokonut.client import KokonutClient, AuthenticationError, PermissionError

client = KokonutClient(
    base_url="http://localhost:8055",
    token="your-directus-static-token",  # Scoped to agent role
)

# List verified harvest events
harvests = client.harvest_events.list()

# Create a draft AI summary
client.create_item("ai_summary", {
    "subject_type": "location",
    "subject_id": LOCATION_ID,
    "summary_type": "operations",
    "content": "Summary text...",
    "status": "draft",  # Agents cannot publish directly
    "source_tables": ["harvest_event"],
    "model_version": "gpt-4o",
    "confidence": 0.87,
})
```

The SDK provides 13 typed method classes: `locations`, `farms`, `plots`, `crop_cycles`, `harvest_events`, `sales_events`, `expense_events`, `sensor_readings`, `wallet_profiles`, `attestations`, `reports`, `exports`, `noi`. Error types: `KokonutError`, `AuthenticationError`, `NotFoundError`, `PermissionError`, `ValidationError`.

### JavaScript/TypeScript SDK

The `@kokonut-intelligence/sdk` package wraps `@directus/sdk`:

```bash
npm install @kokonut-intelligence/sdk
```

```typescript
import { KokonutClient } from "@kokonut-intelligence/sdk";

const client = new KokonutClient("http://localhost:8055", {
  token: "your-directus-static-token",
});

// List verified harvest events
const harvests = await client.harvestEvents.list();

// Create a draft AI summary
await client.createItem("ai_summary", {
  subject_type: "location",
  subject_id: LOCATION_ID,
  summary_type: "operations",
  content: "Summary text...",
  status: "draft",
  source_tables: ["harvest_event"],
  model_version: "gpt-4o",
  confidence: 0.87,
});
```

### Directus MCP Interface

Directus 12.1.1 exposes an MCP-compatible interface that allows AI agents to read and write data. Agents authenticate with scoped tokens and are subject to the same role-based permissions. See the [Directus MCP documentation](https://docs.directus.io/guides/mcp.html) for configuration details.

## Authentication Paths

Agents can authenticate through three paths:

### Path A: Directus Static Token (Recommended for Agents)

Create a Directus user with an agent role, then generate a static token:

```bash
DIRECTUS_URL=${DIRECTUS_URL:-https://localhost/directus}

# Create user for the agent (assign to existing agent role)
curl -k -X POST "$DIRECTUS_URL/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "agent-mrv@kokonut.network",
    "password": "agent-generated-password",
    "role": "a1000000-0000-0000-0000-000000000007"
  }'

# Generate static token via Directus admin UI or API
```

The role UUID determines the permission boundary:
- `a1000000-0000-0000-0000-000000000006` → `Agent Read-Only`
- `a1000000-0000-0000-0000-000000000007` → `Agent Write`
- `a1000000-0000-0000-0000-000000000008` → `Agent Full`

### Path B: Gateway API Key (Service-to-Service)

The Kokonut Gateway uses API keys with `name:resource:action` scope format:

```bash
# Set in environment
export KOKONUT_API_KEYS="your-api-key:agent-mrv"
export KOKONUT_API_KEY_SCOPES="agent-mrv:agent_task:create,agent-mrv:ai_summary:create"
```

Scope format: `name:resource:action` where `resource` or `action` may be `*` for wildcards. Keys with no configured scopes are denied access to every non-public route (fail-closed). The Directus admin token gets full access by design.

### Path C: Capability Tokens

Capability tokens provide time-scoped, resource-bounded access for specific agent operations. See `services/security/` for issuance and validation.

## Permission Boundaries

### Agent Read-Only (`agent_read_only`)

Read access to verified/published data (`config/directus/permissions.sql:545-565`):

| Collection | Action | Filter |
|------------|--------|--------|
| `farm_activity` | read | `status IN (verified, published)` |
| `harvest_event` | read | `status IN (verified, published)` |
| `expense_event` | read | `status IN (verified, published)` |
| `sales_event` | read | `status IN (verified, published)` |
| `loss_event` | read | `status IN (verified, published)` |
| `labor_event` | read | `status IN (verified, published)` |
| `field_note` | read | (no filter) |
| `mrv_claim` | read | `status IN (verified, published)` |
| `attestation_record` | read | `status IN (verified, published)` |
| `agent_identity` | read | (no filter) |
| `agent_task` | read | (no filter) |
| `ai_summary` | read | `status IN (verified, published)` |
| `metric_definition` | read | (no filter) |
| `forecast_scenario` | read | (no filter) |
| `forecast_output` | read | (no filter) |

### Agent Write (`agent_write`)

Create draft records and manage agent tables (`config/directus/permissions.sql:567-591`):

| Collection | Action | Fields |
|------------|--------|--------|
| `mrv_claim` | create | `claim_type, claim_date, claim_data, source_record_ids, evidence_urls, location_id, plot_id` |
| `field_note` | create | `note_date, note_type, title, content, images, tags, plot_id, crop_cycle_id, location_id` |
| `agent_identity` | create | `agent_name, agent_state, metadata, operator_wallet` |
| `agent_task` | create | `task_type, inputs, subject_id, subject_type, requested_by` |
| `agent_task` | update | `execution_status, output, error_message` |
| `agent_action_log` | create | `task_id, action, collection, record_id, payload_hash, action_result, metadata` |
| `ai_summary` | create | `subject_type, subject_id, summary_type, content, source_record_ids, source_tables, model_version, confidence` |

Plus read access to: `harvest_event`, `expense_event`, `sales_event`, `metric_definition`, `forecast_scenario`, `forecast_output`, `agent_identity`, `agent_task`, `agent_action_log`, `ai_summary`.

### Agent Full (`agent_full`)

Broader write access with approval gates (`config/directus/permissions.sql:593-626`):

| Collection | Action | Fields |
|------------|--------|--------|
| `farm_activity` | create | `activity_type, activity_date, description, labor_hours, labor_cost, materials_used, evidence_urls, notes, plot_id, crop_cycle_id, location_id` |
| `harvest_event` | create | `harvest_date, quantity, unit, quality_grade, destination, loss_amount, loss_unit, loss_reason, loss_estimated_value, evidence_urls, notes, plot_id, crop_cycle_id, location_id` |
| `expense_event` | create | `expense_date, category, subcategory, description, vendor, amount, currency, is_capex, allocation_method, allocation_weight, evidence_urls, invoice_number, notes, plot_id, crop_cycle_id, location_id` |
| `mrv_claim` | create/update | All fields + `status, review_notes` on update |
| `attestation_request` | create | `subject_type, subject_id, event_type, location_id` |

Plus all Agent Write permissions, plus read access to: `attestation_record`, `attestation_request`, `workflow_history`, `expense_category`.

**No agent role can publish.** The `publish` action is restricted to human roles via Directus RBAC and enforced by four independent layers.

## Enforcement Architecture

Agent safety is enforced across four defense-in-depth layers:

```
Agent Module (Python)
    |
    | 1. Python preflight guard
    |    assert_agent_action_allowed() -> assess_agent_action()
    |    Raises ValueError if not allowed
    |
    v
Directus API Request
    |
    | 2. Directus hook filter
    |    resolveUserRoles() -> isAgentActorByRoles()
    |    enforceAgentTaskSafety / enforceAiSummarySafety /
    |    enforceStakeholderGovernanceSafety
    |    Throws Error if not allowed
    |
    v
PostgreSQL Write
    |
    | 3. Database CHECK constraints
    |    chk_ai_summary_agent_draft_only
    |    chk_agent_task_draft_submit_only
    |
    v
Audit Log
    |
    | 4. agent_action_log entry
    |    high_risk, requires_human_approval,
    |    payload_hash, metadata JSONB
```

- **Layer 1 (Python):** Every agent module calls `assert_agent_action_allowed()` before writes. See `services/agents/safety.py`.
- **Layer 2 (Hooks):** Directus filter hooks run before DB writes on `agent_task`, `ai_summary`, and all `STAKEHOLDER_HUMAN_REVIEW_COLLECTIONS`. See `extensions/kokonut-hooks/src/agent-safety.ts`.
- **Layer 3 (DB):** CHECK constraints restrict status fields for agent-created records. See `schemas/postgres/029_impact_accountability_foundation.sql`.
- **Layer 4 (Audit):** Every action is logged to `agent_action_log` with tamper-evident `payload_hash`.

For full enforcement details, see [Agent Safety](agent-safety.md).

## Audit Logging

Three tables capture different aspects of agent activity:

### `agent_action_log` — Agent-Specific Audit

The dedicated agent audit trail, written by `services/agents/logging.py:log_agent_action()`:

```sql
-- View all agent actions
SELECT
    aal.action,
    aal.collection,
    aal.record_id,
    aal.action_result,
    aal.high_risk,
    aal.requires_human_approval,
    aal.payload_hash,
    aal.metadata,
    aal.created_at
FROM agent_action_log aal
ORDER BY aal.created_at DESC;

-- View only high-risk actions requiring human approval
SELECT aal.action, aal.collection, aal.record_id, aal.created_at
FROM agent_action_log aal
WHERE aal.high_risk = true
  AND aal.requires_human_approval = true
ORDER BY aal.created_at DESC;
```

### `audit_log` — General API Mutations

All API mutations with user context (`schemas/postgres/008_governance.sql`):

```sql
-- Agent audit trail via user email
SELECT al.timestamp, al.user_email, al.action, al.collection, al.record_id, al.new_data
FROM audit_log al
WHERE al.user_email LIKE '%agent%'
ORDER BY al.timestamp DESC;
```

### `workflow_history` — Lifecycle Transitions

Status transitions recorded by Directus hooks (`schemas/postgres/009_operations_ux.sql`):

```sql
-- View lifecycle transitions for agent-created records
SELECT wh.collection, wh.record_id, wh.from_status, wh.to_status, wh.changed_at, wh.notes
FROM workflow_history wh
WHERE wh.notes LIKE '%agent%'
ORDER BY wh.changed_at DESC;
```

## Capability Manifests

Agents publish capability manifests as versioned JSON with CID pinning:

```bash
# Print an example manifest
python3 -m services.agents --example kokonut-mrv-reporter

# Validate and optionally pin to local CID store
python3 -m services.agents --validate manifest.json --pin-local
```

Manifest structure:

```json
{
  "agent_name": "kokonut-mrv-reporter",
  "version": "1.0.0",
  "description": "Prepares MRV events and EAS attestation request metadata.",
  "inputs": {
    "farm_id": {"type": "string", "required": true},
    "period_start": {"type": "string", "format": "ISO8601", "required": true},
    "period_end": {"type": "string", "format": "ISO8601", "required": true}
  },
  "outputs": {
    "mrv_event_id": {"type": "string", "format": "uuid"},
    "eas_attestation_uid": {"type": "string"},
    "ipfs_cid": {"type": "string"}
  },
  "pricing": {"token": "USDC", "chain": "base", "per_task_usd": 5.0},
  "marketplace_logic": "Kokonut-Agentic-Marketplace"
}
```

Required fields: `agent_name`, `version`, `description`, `inputs`, `outputs`. The `prepare_manifest()` function validates structure and computes CID/hash metadata.

## SDK Reference

Three SDKs are available:

### Python (`kokonut-intelligence` v0.1.0)

- **Location:** `sdk/python/`
- **Dependencies:** `requests>=2.28.0`, `psycopg2-binary>=2.9.9`
- **Client:** `kokonut.client.KokonutClient(base_url, token=...)`
- **Methods:** `locations`, `farms`, `plots`, `crop_cycles`, `harvest_events`, `sales_events`, `expense_events`, `sensor_readings`, `wallet_profiles`, `attestations`, `reports`, `exports`, `noi`
- **Errors:** `KokonutError`, `AuthenticationError`, `NotFoundError`, `PermissionError`, `ValidationError`
- **Generic CRUD:** `list_items()`, `get_item()`, `create_item()`, `create_items()`, `update_item()`, `delete_item()`, `aggregate()`

### JavaScript (`@kokonut-intelligence/sdk` v0.1.0)

- **Location:** `sdk/javascript/`
- **Dependencies:** `@directus/sdk` ^17.0.0
- **Client:** `new KokonutClient(baseUrl, { token })`
- **Methods:** Same 13 typed method classes as Python
- **Generic CRUD:** `listItems()`, `getItem()`, `createItem()`, `createItems()`, `updateItem()`, `deleteItem()`

### TypeScript gRPC (`@kokonut/intelligence-client` v1.0.0)

- **Location:** `sdk/typescript/`
- **Dependencies:** `@grpc/grpc-js` ^1.12.0, `google-protobuf` ^3.21.4
- **Client:** `KokonutGrpcClient` wrapping gRPC transport
- **Use case:** High-performance service-to-service communication via the Kokonut gRPC server

## Troubleshooting

### Agent gets 403 Forbidden

The agent token lacks permission for the requested collection/action. Check:
1. The agent's Directus role in admin UI — verify the role has the required policy
2. The `directus_permissions` row for the role's policy, collection, and action
3. Python-side: `assess_agent_action()` may be blocking the action — check the `SafetyDecision.reason`

### Agent gets 401 Unauthorized

The token is invalid or expired. For Directus static tokens, regenerate via admin UI. For gateway API keys, verify `KOKONUT_API_KEYS` and `KOKONUT_API_KEY_SCOPES` environment variables.

### Agent creates records with unexpected status

Verify the Directus permission `filters` restrict status transitions. The Python safety layer (`services/agents/safety.py`) and Directus hooks (`extensions/kokonut-hooks/src/agent-safety.ts`) independently enforce that agents can only create records with `status = 'draft'` or `review_status = 'draft'`.

### Audit log shows no agent activity

Ensure the agent is using its own static token, not the admin token. Agent actions are logged to `agent_action_log` via `log_agent_action()` — check both `agent_action_log` and `audit_log` (the Directus built-in audit trail).

### Python SDK throws PermissionError

The SDK raises `kokonut.client.PermissionError` on 403 responses. This means the Directus role's permissions do not cover the requested action. Review the role's permission rows in `config/directus/permissions.sql`.
