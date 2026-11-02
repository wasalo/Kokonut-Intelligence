# Agent Workflows

Kokonut agents assist with drafts, exports, synthesis, and review preparation. They do not replace human governance. Enforcement varies by execution path: Python policy and task validation cover guarded code paths, Directus hooks cover selected Directus writes, two database constraints cover specific status fields, and audit calls are explicit rather than automatic. Database least privilege for agent identities is not complete. See [Agent Safety](agent-safety.md) for exact coverage and [Agent Access](agent-access.md) for connection and permission reference.

## Task Catalogue

The task catalogue lives in `services/agents/tasks.py` (20 registered tasks). No task declares `high_risk: True`; task write targets and lifecycle values are checked by the shared task and Python safety paths.

### Read-Only Tasks

| Task | Description | Writes | Risk |
|------|-------------|--------|------|
| `cids_export` | Prepare a CIDS v3.2.0 Essential Tier JSON-LD export for one location | None | Low |
| `public_interest_report_context` | Prepare report limitations, evidence gaps, and public stakeholder voice | None | Low |
| `ebf_evidence_gap` | Analyze EBF score evidence gaps by pillar, maturity level, and public readiness | None | Low |

### Synthesis Tasks

Location-based synthesis tasks require an exact `--location-id UUID`; they do not fall back to network-wide reads. Applicable synthesis CLIs accept `--store` to persist a draft `ai_summary`.

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

### Signed Synthesis Worker Tasks

These two location-bound synthesis tasks are registered in the same catalogue
but execute through the signed worker path rather than standalone CLI modules.

| Task | Description | Writes | Risk |
|------|-------------|--------|------|
| `ecological_modeling_synthesis` | Build an advisory ecological summary from signed, exact-location source projections | `ai_summary:draft` | Medium |
| `organic_readiness_synthesis` | Build an advisory organic-readiness summary from signed, exact-location source projections | `ai_summary:draft` | Medium |

### Task Catalogue CLI

```bash
# List all registered task keys
python3 -m services.agents.tasks --list

# Print full definition for one task
python3 -m services.agents.tasks --describe feedback_synthesis
python3 -m services.agents.tasks --describe ebf_scorecard_draft
```

## CLI Agents

15 agent CLI entry points are invokable via `python3 -m`; all accept `--help`. Two additional signed synthesis modules (`ecological_modeling_agent` and `organic_readiness_agent`) run through the worker path and do not expose standalone CLIs.

### AI Summary

| Command | Required | Optional | Description |
|---------|----------|----------|-------------|
| `python3 -m services.agents.ai_summary` | `--location-id UUID` | `--summary-type {operations,financial,environmental,combined}`, `--store`, `--list`, `--verify SUMMARY_ID` | Generate structured text summary from governed data. Requires verified/published `farm_registry_record`. List and digest inspection require the exact `--location-id`; they use the signed `ai_summary/read` source identity. `--verify` computes a digest only and does not approve or change lifecycle state. |

### CIDS Export

| Command | Required | Optional | Description |
|---------|----------|----------|-------------|
| `python3 -m services.agents.cids_agent` | `--location-id UUID` | `--summary` | Prepare CIDS v3.2.0 Essential Tier JSON-LD export. Read-only. |

### Synthesis Agents

All standalone location-based synthesis CLIs listed below require
`--location-id UUID`; `--store` persists a draft where supported.

| Command | `--location-id` | Description |
|---------|-----------------|-------------|
| `python3 -m services.agents.feedback_agent` | Required | Summarize stakeholder feedback |
| `python3 -m services.agents.wellbeing_agent` | Required | Summarize well-being metrics and cultural context |
| `python3 -m services.agents.resilience_agent` | Required | Summarize financial resilience and scaling |
| `python3 -m services.agents.capital_efficiency_agent` | Required | Summarize capital efficiency and governance throughput |
| `python3 -m services.agents.commons_agent` | Required | Summarize commons liberation and stewardship |
| `python3 -m services.agents.gnh_agent` | Required | Summarize GNH alignment and cultural preservation |
| `python3 -m services.agents.regenerator_agent` | Required | Summarize regenerative outcomes and community governance |
| `python3 -m services.agents.open_source_capitalist_agent` | Required | Summarize scaling economics and adoption barriers |
| `python3 -m services.agents.kokonut_commons_agent` | Required | Summarize anti-capture governance and federation |
| `python3 -m services.agents.bio_factory_agent` | Required | Summarize bio-factory operations and LAC regional inputs |

### EBF Agents

| Command | Required | Description |
|---------|----------|-------------|
| `python3 -m services.agents.ebf_scorecard_agent` | `--location-id UUID`, `--period-start YYYY-MM-DD`, `--period-end YYYY-MM-DD` | Draft EBF scorecard workspace |
| `python3 -m services.agents.ebf_evidence_gap_agent` | `--scorecard-id UUID`, `--location-id UUID` | Analyze evidence gaps for a scorecard within an explicit location |
| `python3 -m services.agents.ebf_calibration_agent` | `--session-id UUID` | Draft calibration memo |

### Delphi Facilitator

| Command | Required | Optional | Description |
|---------|----------|----------|-------------|
| `python3 -m services.agents.delphi_facilitator_agent` | `--study-id UUID` | `--draft`, `--recommendation-text "..."` | Facilitate Delphi study; `--draft` also creates a recommendation draft |

## Signed Synthesis Workers

The `ecological_modeling_synthesis` and `organic_readiness_synthesis` tasks
run through signed worker modules and require an exact location. They
remain advisory drafts and do not replace ecological field validation or
certification by an accredited body. Ecological modeling is not a deterministic
prediction. The ecological task keeps its legacy calculations while resolving
their relation names only through signed, exact-location source projections.

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

Every location-based synthesis requires a valid location UUID. A missing or
blank location is rejected before source queries; no synthesis agent silently
widens its scope to all locations.

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

For enforcement coverage and the explicit limits of each layer, see [Agent Safety](agent-safety.md).

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
# Agent safety policy and database-boundary tests
python3 -m tests.test_agent_safety

# Agent task catalogue and input/output validation tests
python3 -m tests.test_agent_tasks

# Directus hook tests (includes agent safety enforcement)
cd extensions/kokonut-hooks && npm test
```

### Test Coverage

| Test File | Tests | What It Validates |
|-----------|-------|-------------------|
| `tests/test_agent_safety.py` | 7 | Payload hash stability, publish blocking, high-risk action flagging, governed collection coverage, stakeholder write protection, agent read access |
| `tests/test_agent_tasks.py` | 5 | Task catalogue completeness, output validation, CIDS agent output, feedback privacy guard, EBF publish/maturity blocking |
