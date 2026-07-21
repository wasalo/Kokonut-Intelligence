# Agent Safety

Kokonut agents assist with drafts, exports, synthesis, and review preparation. They do not replace human governance. Every agent write is guarded by four enforcement layers that prevent agents from verifying, publishing, or modifying human-governed records.

## Rules

1. **Agents can create draft outputs.** Agents may write records with status `draft`, `submitted`, or `rejected` on governed collections.
2. **Agents can submit or reject their own outputs** where hooks allow it. Agents may transition their own `agent_task` and `ai_summary` records between draft, submitted, and rejected.
3. **Agents cannot verify or publish their own outputs.** The statuses `verified` and `published` are reserved for human actors.
4. **High-risk actions require human approval and audit logging.** Any action in `HIGH_RISK_ACTIONS` is automatically flagged for human review.

## Governed Collections

The constant `GOVERNED_COLLECTIONS` in `services/agents/safety.py` defines **167 collection names** that agents cannot freely write to. This includes:

- **Agent outputs:** `ai_summary`, `agent_task`, `ebf_scorecard`, `ebf_score`, `ebf_calibration_decision`
- **Stakeholder records:** `stakeholder_feedback`, `impact_claim`, `metric_proposal`, `party`, `party_identifier`, `party_relationship`, and all stakeholder engagement/grievance/decision collections
- **Market & cooperative:** `buyer_verification`, `market_dispute`, `cooperative_distribution_decision`
- **Coordination:** `coordination_alliance`, `coordination_participant`, `coordination_objective`, and related collections
- **Trust & governance:** `party_trust_evidence`, `governance_circle`, `governance_role`, `governance_proposal`, `governance_tension`, and tactical collections
- **Financial:** `financial_sustainability_plan`, `farm_launch_unit_economics`, `capital_efficiency_scenario`, and related collections
- **Carbon & credits:** `carbon_credit`, `credit_adjustment`, `credit_retirement`, `credit_class`, `credit_batch`, `retirement_certificate`, `credit_balance`
- **Data stream:** `data_stream_post`, `data_stream_post_comment`
- **Forecasting:** `forecast_scenario`, `forecast_output`, `scenario_parameter`, `scenario_simulation`
- **Threatcasting:** `threat`, `threat_signal`, `threat_narrative`, `backcast_plan`, `backcast_milestone`
- **Capital accounting:** `capital_capacity_assessment`, `capital_diversion_observation`, `capital_capture_risk`, `regenerative_credit_ledger`
- **Governance:** `iri_registry`, `app_project_metadata`, `delphi_study`, `delphi_recommendation`, `report_snapshot`, `dashboard_dataset`

The full set is defined in `services/agents/safety.py:26-192`. Any collection not in this set is unrestricted for agents.

## Human-Review Collections

The constant `STAKEHOLDER_HUMAN_REVIEW_COLLECTIONS` defines **43 collections** in Python (46 in TypeScript, which includes `governance_tension`, `governance_proposal`, and `governance_tactical_item` in the blocked set with explicit exception handling) where agents cannot write at all — not even drafts. These are entirely human-governed:

- All `coordination_*` collections (except `coordination_alliance` draft creation)
- All `governance_circle`, `governance_role`, `governance_role_*` collections
- All `governance_tension_*`, `governance_proposal_*`, `governance_tactical_*` collections (beyond draft creation)
- All `party_trust_evidence`, `stewardship_proxy_authority`, `nature_stewardship_obligation`, `future_generation_principle`
- All stakeholder consent, decision, and grievance collections

Agents may only `read`, `list`, or `query` these collections.

## Draftable Exceptions

Five collections have explicit exceptions where agents **can** create draft records:

| Collection | Allowed action | Required status |
|---|---|---|
| `coordination_alliance` | create | `draft` |
| `governance_tension` | create | `draft` |
| `governance_proposal` | create | `draft` |
| `governance_tactical_item` | create | `open` |
| `regenerative_credit_ledger` | create | `draft` |

Beyond draft creation, agents cannot modify these records.

## High-Risk Actions

The constant `HIGH_RISK_ACTIONS` in `services/agents/safety.py:12-20` defines seven actions:

| Action | What it means |
|---|---|
| `publish` | Make a record publicly visible |
| `attest` | Create an on-chain or off-chain attestation |
| `onchain_submit` | Submit a transaction to a blockchain |
| `delete` | Remove a record from the database |
| `bulk_update` | Modify many records in a single operation |
| `financial_write` | Write to financial records (expenses, sales, revenue) |
| `status_change_to_published` | Transition any record to `published` status |

When a high-risk action is detected:
- The `agent_action_log` entry is auto-tagged with `high_risk = true` and `requires_human_approval = true`
- The action is logged with a `payload_hash` (SHA-256) for tamper-evident audit trails
- Human approval is required before execution

## EBF-Specific Rules

EBF (Ecological Benefit Framework) scorecards have additional constraints:

- Agents can only set status to `draft`, `submitted`, or `rejected` on `ebf_scorecard`, `ebf_score`, and `ebf_calibration_decision` records.
- Agents **cannot** raise `evidence_maturity_level` above **3** on `ebf_scorecard` or `ebf_score` records. Levels 4–6 (third-party verified, externally verified, registry issued) require human review.

## Enforcement Architecture

Agent safety is enforced across four defense-in-depth layers:

```
Agent Module (Python)
    |
    | 1. Python preflight guard
    |    assert_agent_action_allowed() → assess_agent_action()
    |    Raises ValueError if not allowed
    |
    v
Directus API Request
    |
    | 2. Directus hook filter
    |    resolveUserRoles() → isAgentActorByRoles()
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

### Layer 1: Python Preflight Guards

**File:** `services/agents/safety.py`

Every agent module calls `assert_agent_action_allowed(action, collection, payload)` before any write. This function calls `assess_agent_action()` which runs a 10-step decision cascade:

1. Check `coordination_alliance` draft exception
2. Check draftable collection exceptions (`governance_tension`, `governance_proposal`, `governance_tactical_item`, `regenerative_credit_ledger`)
3. Block non-read actions on governance collections beyond draft creation
4. Block non-read actions on `STAKEHOLDER_HUMAN_REVIEW_COLLECTIONS`
5. Check `agent_task.review_status` against allowed statuses
6. Check `ai_summary.status` against allowed statuses
7. Check EBF collection statuses against allowed statuses
8. Check EBF evidence maturity level cap (≤ 3)
9. Check all other governed collection statuses against allowed statuses
10. Block `status_change_to_published` unconditionally

Returns a `SafetyDecision` dataclass:

```python
@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool          # Whether the action is permitted
    high_risk: bool        # Whether the action is in HIGH_RISK_ACTIONS
    requires_human_approval: bool  # Whether human approval is needed
    reason: str            # Human-readable explanation
```

Agents should call `audit_agent_action()` after execution to log the result to `agent_action_log`.

### Layer 2: Directus Hook Filters

**File:** `extensions/kokonut-hooks/src/agent-safety.ts`

Hooks run as `filter` hooks (before DB write) on:
- `agent_task.create` and `agent_task.update` → `enforceAgentTaskSafety`
- `ai_summary.create` and `ai_summary.update` → `enforceAiSummarySafety`
- `agent_action_log.create` → `prepareAgentActionLog`
- Every collection in `STAKEHOLDER_HUMAN_REVIEW_COLLECTIONS` → `.create` and `.update` → `enforceStakeholderGovernanceSafety`

**Role identification** uses `isAgentActorByRoles(roles)` which checks for resolved role slugs:
- `agent_read_only` — read-only agent access
- `agent_write` — agent can create limited records
- `agent_full` — agent with full write access
- Any role slug starting with `agent`

**Critical security property:** Role resolution uses `resolveUserRoles()` from `extensions/kokonut-hooks/src/roles.ts`, which reads `meta.accountability` (server-provided). It **never** trusts `payload._accountability` (client-supplied). The role cache has a 5-minute TTL.

### Layer 3: Database Constraints

**File:** `schemas/postgres/029_impact_accountability_foundation.sql`

Two CHECK constraints enforce agent safety at the database level:

**`chk_ai_summary_agent_draft_only`:**
```sql
CHECK (created_by IS NULL OR status IN ('draft', 'submitted', 'rejected'))
```
If `created_by` is set (agent-created), status is restricted. If `created_by` is NULL (human-created), any status is allowed.

**`chk_agent_task_draft_submit_only`:**
```sql
CHECK (review_status IN ('draft', 'submitted', 'rejected'))
```
Unconditionally restricts `agent_task.review_status` for all records, not just agent-created ones.

### Layer 4: Audit Logging

**File:** `services/agents/logging.py`

Every agent action is logged to `agent_action_log` with the following schema:

| Column | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `agent_id` | UUID FK | References `agent_identity(id)` |
| `task_id` | UUID FK | References `agent_task(id)` |
| `action` | VARCHAR(100) | Action performed |
| `collection` | VARCHAR(100) | Target collection |
| `record_id` | UUID | Target record |
| `payload_hash` | VARCHAR(64) | SHA-256 hash of payload for tamper evidence |
| `action_result` | VARCHAR(50) | `success`, `failed`, or `skipped` |
| `error_message` | TEXT | Error details if failed |
| `metadata` | JSONB | Contains `allowed`, `reason`, `requires_human_approval` |
| `high_risk` | BOOLEAN | Auto-set for HIGH_RISK_ACTIONS |
| `requires_human_approval` | BOOLEAN | Auto-set for HIGH_RISK_ACTIONS |
| `created_at` | TIMESTAMPTZ | Timestamp |

Directus permissions for agent roles:
- `agent_read_only`: can read `agent_action_log`
- `agent_write` and `agent_full`: can create (limited columns) and read

## Agent Roles

Three Directus roles are provisioned for agent access:

| Role | Permissions |
|---|---|
| `agent_read_only` | Read-only access to governed collections and audit logs |
| `agent_write` | Can create draft records on permitted collections, read audit logs |
| `agent_full` | Same as `agent_write` with broader collection access |

All agent roles are identified by resolved role slugs (lowercase, underscored), never by raw UUIDs. The `resolveUserRoles()` function in `extensions/kokonut-hooks/src/roles.ts` converts the Directus role name to a slug and caches it for 5 minutes.

## Agent Task Catalogue

The task catalogue in `services/agents/tasks.py` defines **21 tasks** with explicit risk levels and write permissions:

| Task | Risk | Writes | Description |
|---|---|---|---|
| `cids_export` | low | none | Read-only CIDS v3.2.0 JSON-LD export |
| `feedback_synthesis` | medium | `ai_summary:draft` | Summarize stakeholder feedback |
| `public_interest_report_context` | low | none | Report limitations and stakeholder voice |
| `holistic_wellbeing_synthesis` | medium | `ai_summary:draft` | Cultural context, well-being metrics |
| `financial_resilience_synthesis` | medium | `ai_summary:draft` | Financial sustainability, scaling |
| `capital_efficiency_synthesis` | medium | `ai_summary:draft` | Capital efficiency, governance throughput |
| `commons_liberation_synthesis` | medium | `ai_summary:draft` | Time liberation, capital alignment |
| `gnh_alignment_synthesis` | medium | `ai_summary:draft` | GNH, cultural, renewable evidence |
| `regenerator_synthesis` | medium | `ai_summary:draft` | Regenerative outcomes, community governance |
| `open_source_capitalist_synthesis` | medium | `ai_summary:draft` | Scaling economics, adoption barriers |
| `kokonut_commons_synthesis` | medium | `ai_summary:draft` | Anti-capture, redistribution, federation |
| `bio_factory_synthesis` | medium | `ai_summary:draft` | Bio-organic fertilizer operations |
| `ai_summary_synthesis` | medium | `ai_summary:draft` | General operations/financial/environmental summary |
| `ebf_scorecard_draft` | medium | `ebf_scorecard:draft`, `ebf_score:draft` | Draft EBF scorecard workspace |
| `ebf_evidence_gap` | low | none | Read-only EBF evidence gap analysis |
| `ebf_calibration_memo` | medium | `ebf_calibration_decision:draft` | Draft calibration memo |
| `delphi_facilitation` | medium | `delphi_recommendation:draft` | Delphi study facilitator |
| `coordination_strategy_draft` | medium | `coordination_alliance:draft` | Draft coordination alliance options |

**No tasks have `high_risk: True`.** All tasks write only draft records.

## Agent CLI Commands

```bash
# List all available tasks
python3 -m services.agents.tasks --list

# Run specific agents
python3 -m services.agents.cids_agent --location-id <uuid> --summary
python3 -m services.agents.feedback_agent --location-id <uuid>
python3 -m services.agents.wellbeing_agent --location-id <uuid>
python3 -m services.agents.resilience_agent --location-id <uuid>
python3 -m services.agents.capital_efficiency_agent --location-id <uuid>
python3 -m services.agents.commons_agent --location-id <uuid>
python3 -m services.agents.gnh_agent --location-id <uuid>
python3 -m services.agents.regenerator_agent --location-id <uuid>
python3 -m services.agents.open_source_capitalist_agent --location-id <uuid>
python3 -m services.agents.kokonut_commons_agent --location-id <uuid>
python3 -m services.agents.bio_factory_agent --location-id <uuid>
python3 -m services.agents.ecological_modeling_agent --location-id <uuid>
python3 -m services.agents.organic_readiness_agent --location-id <uuid>
python3 -m services.agents.ebf_scorecard_agent --help
python3 -m services.agents.ebf_evidence_gap_agent --help
python3 -m services.agents.ebf_calibration_agent --help
python3 -m services.agents.delphi_facilitator_agent --study-id <uuid> --draft
```

## Reviewer Responsibility

Reviewers may use agent outputs as evidence preparation, but final publication, attestation submission, and public claims remain human-approved decisions. Agent-generated `ai_summary` records require a verified/published `farm_registry_record` before generation.

## Testing

```bash
# Run agent safety tests
python3 -m tests.test_agent_safety

# Run Directus hook tests (includes agent safety enforcement)
cd extensions/kokonut-hooks && npm test
```

## Security Properties

The agent safety system maintains these invariants:

1. **No self-publishing.** Agents cannot set any record to `verified` or `published` status.
2. **No human-governed writes.** Agents cannot create or update records in `STAKEHOLDER_HUMAN_REVIEW_COLLECTIONS` (except 5 draftable exceptions).
3. **No high-risk actions without audit.** All high-risk actions are logged with `high_risk=true` and `requires_human_approval=true`.
4. **Tamper-evident audit.** Every action log entry includes a `payload_hash` (SHA-256) for integrity verification.
5. **Role-based identification.** Agent actors are identified by resolved role slugs from `meta.accountability`, never by client-supplied fields.
6. **Defense in depth.** Four enforcement layers (Python, hooks, DB constraints, audit) ensure no single point of failure.
7. **EBF maturity cap.** Agents cannot raise EBF evidence maturity above level 3 (third-party verified and above require human review).
8. **No autonomous intervention.** Threatcasting, Delphi, tactical, reserve, and simulation outputs do not authorize autonomous intervention, fund release, stakeholder manipulation, or on-chain execution.
