# Agent Workflows

Kokonut agents assist with drafts, exports, synthesis, and review preparation. They do not replace human governance. Every agent write is guarded by four enforcement layers that prevent agents from verifying, publishing, or modifying human-governed records. See [Agent Safety](agent-safety.md) for full enforcement details and [Agent Access](agent-access.md) for connection and permission reference.

## Task Catalogue

The task catalogue lives in `services/agents/tasks.py` (18 registered tasks). No task has `high_risk: True`; all write targets are draft-only.

### Read-Only Tasks

| Task | Description | Writes | Risk |
|------|-------------|--------|------|
| `cids_export` | Prepare a CIDS v3.2.0 Essential Tier JSON-LD export for one location | None | Low |
| `public_interest_report_context` | Prepare report limitations, evidence gaps, and public stakeholder voice | None | Low |
| `ebf_evidence_gap` | Analyze EBF score evidence gaps by pillar, maturity level, and public readiness | None | Low |

### Synthesis Tasks

All synthesis tasks produce structured JSON summaries from governed data. Most accept `--location-id` (optional for network-wide) and `--store` (persist draft `ai_summary`).

| Task | Description | Writes | Risk |
|------|-------------|--------|------|
| `ai_summary_synthesis` | Generate operations, financial, or environmental summary with registry-backed location check | `ai_summary:draft` | Medium |
| `feedback_synthesis` | Summarize public stakeholder feedback and aggregate private/no-consent signals | `ai_summary:draft` | Medium |
| `holistic_wellbeing_synthesis` | Summarize cultural context, well-being metrics, language coverage, and participatory actions | `ai_summary:draft` | Medium |
| `financial_resilience_synthesis` | Summarize financial sustainability, risk mitigation, scaling roadmap, and publication status | `ai_summary:draft` | Medium |
| `capital_efficiency_synthesis` | Summarize capital efficiency, regenerative payback, governance throughput, and capital-provider scenarios | `ai_summary:draft` | Medium |
| `commons_liberation_synthesis` | Summarize time liberation, capital alignment, governance inclusion, and land stewardship evidence | `ai_summary:draft` | Medium |
| `gnh_alignment_synthesis` | Summarize GNH alignment, cultural preservation, renewable energy, vulnerable access, and well-being evidence | `ai_summary:draft` | Medium |
| `regenerator_synthesis` | Summarize regenerative outcomes, community governance, replication readiness, and adaptive stewardship | `ai_summary:draft` | Medium |
| `open_source_capitalist_synthesis` | Summarize scaling economics, adoption barriers, perpetual-value stress tests, and open-source reuse | `ai_summary:draft` | Medium |
| `kokonut_commons_synthesis` | Summarize anti-capture governance, redistribution policies, federation protocols, and participatory signals | `ai_summary:draft` | Medium |
| `bio_factory_synthesis` | Summarize bio-organic fertilizer batches, input provenance, recipes, quality tests, and LAC regional availability | `ai_summary:draft` | Medium |

### EBF Tasks

| Task | Description | Writes | Risk |
|------|-------------|--------|------|
| `ebf_scorecard_draft` | Draft an EBF scorecard workspace from governed source metrics and evidence links | `ebf_scorecard:draft`, `ebf_score:draft` | Medium |
| `ebf_calibration_memo` | Draft a calibration memo from reviewed scorecards and documented evidence | `ebf_calibration_decision:draft` | Medium |

### Coordination & Delphi Tasks

| Task | Description | Writes | Risk |
|------|-------------|--------|------|
| `coordination_strategy_draft` | Draft candidate coordination alliances from stakeholder, capability, market, trust, and cooperative evidence | `coordination_alliance:draft` | Medium |
| `delphi_facilitation` | Facilitate Real-time Delphi studies: anonymized live summary and draft recommendation | `delphi_recommendation:draft` | Medium |

### Task Catalogue CLI

```bash
# List all registered task keys
python3 -m services.agents.tasks --list

# Print full definition for one task
python3 -m services.agents.tasks --describe feedback_synthesis
python3 -m services.agents.tasks --describe ebf_scorecard_draft
```

## CLI Agents

15 agent modules are invokable via `python3 -m`. All accept `--help`.

### AI Summary

| Command | Required | Optional | Description |
|---------|----------|----------|-------------|
| `python3 -m services.agents.ai_summary` | `--location-id UUID` | `--summary-type {operations,financial,environmental,combined}`, `--store`, `--list`, `--verify ID` | Generate structured text summary from governed data. Requires verified/published `farm_registry_record`. |

### CIDS Export

| Command | Required | Optional | Description |
|---------|----------|----------|-------------|
| `python3 -m services.agents.cids_agent` | `--location-id UUID` | `--summary` | Prepare CIDS v3.2.0 Essential Tier JSON-LD export. Read-only. |

### Synthesis Agents

All synthesis agents share the same pattern: `--location-id UUID` (required or optional) and `--store` (persist draft).

| Command | `--location-id` | Description |
|---------|-----------------|-------------|
| `python3 -m services.agents.feedback_agent` | Required | Summarize stakeholder feedback |
| `python3 -m services.agents.wellbeing_agent` | Required | Summarize well-being metrics and cultural context |
| `python3 -m services.agents.resilience_agent` | Optional | Summarize financial resilience and scaling |
| `python3 -m services.agents.capital_efficiency_agent` | Optional | Summarize capital efficiency and governance throughput |
| `python3 -m services.agents.commons_agent` | Optional | Summarize commons liberation and stewardship |
| `python3 -m services.agents.gnh_agent` | Optional | Summarize GNH alignment and cultural preservation |
| `python3 -m services.agents.regenerator_agent` | Optional | Summarize regenerative outcomes and community governance |
| `python3 -m services.agents.open_source_capitalist_agent` | Optional | Summarize scaling economics and adoption barriers |
| `python3 -m services.agents.kokonut_commons_agent` | Optional | Summarize anti-capture governance and federation |
| `python3 -m services.agents.bio_factory_agent` | Optional | Summarize bio-factory operations and LAC regional inputs |

### EBF Agents

| Command | Required | Description |
|---------|----------|-------------|
| `python3 -m services.agents.ebf_scorecard_agent` | `--location-id UUID`, `--period-start YYYY-MM-DD`, `--period-end YYYY-MM-DD` | Draft EBF scorecard workspace |
| `python3 -m services.agents.ebf_evidence_gap_agent` | `--scorecard-id UUID` | Analyze evidence gaps for a scorecard |
| `python3 -m services.agents.ebf_calibration_agent` | `--session-id UUID` | Draft calibration memo |

### Delphi Facilitator

| Command | Required | Optional | Description |
|---------|----------|----------|-------------|
| `python3 -m services.agents.delphi_facilitator_agent` | `--study-id UUID` | `--draft`, `--recommendation-text "..."` | Facilitate Delphi study; `--draft` also creates a recommendation draft |

## Library-Only Agents

Two agent modules expose programmatic `synthesize_*()` functions but have no CLI entry point. They are not registered in the task catalogue and must be called from Python code:

| Module | Function | Signature |
|--------|----------|-----------|
| `services.agents.ecological_modeling_agent` | `synthesize_ecological_modeling` | `(conn, location_id: str) -> dict[str, Any]` |
| `services.agents.organic_readiness_agent` | `synthesize_organic_readiness` | `(conn, location_id: str) -> dict[str, Any]` |

Both are advisory-only — outputs are not deterministic predictions or certification guarantees.

## Common Patterns

### The `--store` Flag

Most synthesis agents accept `--store` to persist the output as a draft `ai_summary` record. Without `--store`, the agent prints JSON to stdout without writing to the database:

```bash
# Print summary to stdout (no DB write)
python3 -m services.agents.feedback_agent --location-id UUID

# Print AND store as draft ai_summary for human review
python3 -m services.agents.feedback_agent --location-id UUID --store
```

### The `--location-id` Pattern

Some agents require `--location-id` (feedback, wellbeing, ai_summary, CIDS, EBF scorecard). Others accept it as optional — when omitted, they operate across all locations. The `--location-id` is always a UUID.

### Output Format

All agents print JSON to stdout. The JSON structure matches the task's output schema defined in `services/agents/tasks.py`. Example:

```bash
python3 -m services.agents.cids_agent --location-id UUID --summary
# Output: {"graph_count": 42, "alignment_tier": "essential", "cids_version": "3.2.0"}
```

## Safety Rules

1. **Agents may create draft outputs for human review.** Agents write records with status `draft`, `submitted`, or `rejected` on governed collections.
2. **Agents may submit or reject their own outputs** where workflow hooks allow it (e.g., `agent_task`, `ai_summary`).
3. **Agents may not verify or publish their own outputs.** The statuses `verified` and `published` are reserved for human actors.
4. **High-risk actions require human approval and audit logging.** The seven high-risk actions are: `publish`, `attest`, `onchain_submit`, `delete`, `bulk_update`, `financial_write`, `status_change_to_published`.
5. **Feedback synthesis must not include raw private stakeholder feedback.** Private/no-consent records are aggregate-only; raw text is never exposed in agent outputs.

For full enforcement architecture (4-layer defense-in-depth), see [Agent Safety](agent-safety.md).

## Output Schemas

Output schemas are defined as lightweight dictionaries in `services/agents/tasks.py`. They validate required fields without replacing database constraints, Directus hooks, or human review.

```python
from services.agents.tasks import validate_output

# Validate an agent's output against its task schema
errors = validate_output("cids_export", {"graph_count": 1})
# Returns: ["Missing required output field: document",
#           "Missing required output field: alignment_tier",
#           "Missing required output field: cids_version"]
```

Each task defines `inputs` and `outputs` dictionaries with field types, formats, and required flags. The `validate_output()` function checks that all required output fields are present. This is a lightweight preflight check — it does not replace DB constraints, Directus hooks, or human review.

## Testing

```bash
# Agent safety tests (7 tests)
python3 -m tests.test_agent_safety

# Agent task catalogue tests (5 tests)
python3 -m tests.test_agent_tasks

# Directus hook tests (includes agent safety enforcement)
cd extensions/kokonut-hooks && npm test
```

### Test Coverage

| Test File | Tests | What It Validates |
|-----------|-------|-------------------|
| `tests/test_agent_safety.py` | 7 | Payload hash stability, publish blocking, high-risk action flagging, governed collection coverage, stakeholder write protection, agent read access |
| `tests/test_agent_tasks.py` | 5 | Task catalogue completeness, output validation, CIDS agent output, feedback privacy guard, EBF publish/maturity blocking |
