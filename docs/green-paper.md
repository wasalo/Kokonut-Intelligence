# Kokonut Intelligence Platform — Green Paper

**Version:** 2.0
**Date:** July 2026
**Status:** Codebase Parity Draft
**License:** Apache License 2.0

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Executive Summary](#2-executive-summary)
3. [Problem Statement](#3-problem-statement)
4. [System Architecture](#4-system-architecture)
5. [Data Lifecycle](#5-data-lifecycle)
6. [Evidence Maturity Model](#6-evidence-maturity-model)
7. [CIDS Mapping and Export](#7-cids-mapping-and-export)
8. [Stakeholder Feedback](#8-stakeholder-feedback)
9. [Impact Claims and Metric Proposals](#9-impact-claims-and-metric-proposals)
10. [Agent Safety and Workflows](#10-agent-safety-and-workflows)
11. [Web3 Verification](#11-web3-verification)
12. [Carbon and Environmental Impact](#12-carbon-and-environmental-impact)
13. [Additional Evidence Modules](#13-additional-evidence-modules)
13A. [Operational Intelligence and Decisioning](#13a-operational-intelligence-and-decisioning)
13B. [Precision Agriculture and Ecological Modeling](#13b-precision-agriculture-and-ecological-modeling)
13C. [Financial, Credit, and Market Infrastructure](#13c-financial-credit-and-market-infrastructure)
13D. [Strategy, Planning, and Process Management](#13d-strategy-planning-and-process-management)
13E. [Identity, Linked Data, and Federation](#13e-identity-linked-data-and-federation)
13F. [Resilience, Capital, and Simulation](#13f-resilience-capital-and-simulation)
13G. [Stakeholder, Governance, and Cooperative Operations](#13g-stakeholder-governance-and-cooperative-operations)
14. [Reporting Principles and Public Interest](#14-reporting-principles-and-public-interest)
15. [Common Foundations Checklist](#15-common-foundations-checklist)
16. [Publication Boundaries](#16-publication-boundaries)
17. [Pilot Data: Kokonut Adelphi](#17-pilot-data-kokonut-adelphi)
18. [Glossary and References](#18-glossary-and-references)
- [Appendix A: Review Commands](#appendix-a-review-commands)

---

## 1. Purpose

This Green Paper is the stakeholder document for the Kokonut Intelligence Platform. It reconciles the publication narrative with the implemented repository while preserving privacy and surfacing uncertainty. It remains subject to human stakeholder sign-off before publication.

**Audience:** Funders, impact investors, partners, reviewers, standards bodies, and the broader regenerative agriculture community.

**What this document covers:**

- System architecture, data lifecycle, and role-based access.
- Evidence maturity model (levels 0-6) and public claim eligibility rules.
- CIDS v3.2.0 Essential Tier export for impact data interoperability.
- Stakeholder feedback consent management and public-safe summaries.
- Impact claims, metric proposals, and participatory governance.
- Agent safety constraints and task catalogue.
- Web3 verification via EAS on Celo with private evidence off-chain.
- Carbon and environmental impact tracking with explicit boundaries.
- EBF pillar scoring with trust graph provenance and calibration.
- Seven additional evidence modules: capital efficiency, commons liberation, GNH alignment, regenerative outcomes, open-source capitalist scaling, Kokonut Commons governance, and bio-factory operations.
- Operational intelligence through OODA assessment, CRISP risk scoring, threatcasting, backcasting, Delphi consultation, trend analysis, geostatistics, and systems-thinking tools.
- Precision agriculture through weather and climate forecasts, phenology, irrigation, nutrient budgets, pest management, equipment, yield monitoring, digital twins, mobile offline collection, and advisory workflows.
- Strategy and execution through capability maps, value streams, budgets, objectives, portfolios, process mining, predictive BPM, process control, innovation stage gates, and competitive analysis.
- Linked-data and platform infrastructure through IRIs, RDF/SPARQL, JSON-LD, LinkML, evidence-lineage graphs, governed data streams, durable events, scheduling, federation, gRPC, SDKs, and a unified CLI.
- Resilience and capital infrastructure through strategic reserves, capital accounting, prediction calibration, Monte Carlo stress testing, and human-approved release or credit proposals.
- Reporting principles, public-interest context, and disclaimers.
- Pilot data for Kokonut Adelphi, the canonical proof farm.

**What this document does NOT claim:**

- The platform can govern internal credit classes, batches, balances, custody, and retirements; these records do not constitute external registry recognition or external verification.
- EAS attestations are verification metadata, not automatic proof of external verification.
- Carbon-balance evidence is distinct from carbon credit issuance.
- Agent outputs are draft aids for human review, not publication authority.
- Financial sustainability plans, scaling milestones, and forecasts are planning evidence, not guarantees of revenue, funding, expansion, or risk elimination.
- Holistic well-being, GNH alignment, and cultural preservation signals are learning and accountability evidence, not guarantees of community satisfaction or cultural representation.

**How to use this document:**

Reviewers and partners should use the Evidence Maturity Model (Section 6) and Publication Boundaries (Section 16) as the primary references for interpreting claims. The Common Foundations Checklist (Section 15) provides a pre-publication quality gate. The Glossary (Section 18) defines key terms for non-technical readers.

---

## 2. Executive Summary

Kokonut Intelligence is an open-source intelligence layer for regenerative farm operations, financial performance, ecological outcomes, partner reporting, and Web3 verification. It is designed to make regenerative farm evidence comparable while preserving privacy and surfacing uncertainty.

The platform combines PostgreSQL and Directus as the canonical schema and API layer, ClickHouse for analytical events, Python services for metrics and forecasting, EAS on Celo for public verification metadata, and Gnosis Moloch DAO for treasury governance. The system is built to serve farm operators, partners, reviewers, and the broader regenerative agriculture community.

### Core Principles

1. **The schema is the product.** Dashboards, spreadsheets, agents, and blockchain views are interfaces. The durable asset is the canonical schema, metric dictionary, verification logic, and API contract.

2. **Web3 is a proof layer, not source of truth.** Canonical operational and financial data lives in PostgreSQL. Blockchain provides proofs, coordination, and public verifiability.

3. **Humans and AI agents use the same governed objects.** Different interfaces over the same canonical objects, permissions, and audit trails.

4. **Private evidence stays off-chain by default.** Public surfaces store hashes, CIDs, attestation UIDs, chain labels, and transaction hashes. Raw private MRV payloads remain in controlled off-chain storage.

### Key Capabilities

| Category | Capability | What it provides |
|---|---|---|
| **Data Infrastructure** | Governed schema | Versioned PostgreSQL schema with 331 ordered migrations, role-based access, and Directus workflows. |
| | Multi-source ingestion | Weather, market prices, remote sensing, sensors, EAS attestations, and Gnosis DAO activity. |
| | Versioned metrics | Calculator-backed metrics, governed metric definitions, public aggregate views, dashboard datasets, and separate human verification. |
| | Evidence maturity | Levels 0-6 enforced across claims, feedback, MRV, and reporting. |
| **Verification & Interoperability** | CIDS export | v3.2.0 Essential Tier JSON-LD export for impact data interoperability. |
| | EAS attestations | Onchain/offchain attestations on Celo with attester-gating via KokonutResolver. |
| **Reporting & Transparency** | Report snapshots | Public-interest context, limitations, uncertainty notes, and negative findings. |
| | EBF pillar scoring | 7 dimensions, 70 rubric bands, public scorecards, trust graph provenance, and calibration workflow.^[29]^ |
| | Portfolio roll-up | Messy roll-up comparison by pillar, confidence, and maturity with explicit caveats, not farm ranking.^[30]^ |
| | Holistic well-being | Cultural context, local-language reporting, community trust, operator capability, and feedback-to-action traceability.^[33]^ |
| **Impact Domains** | Financial resilience | Grant dependency, reinvestment, public-goods allocation, runway, risk mitigation, scaling milestones, and publication status.^[34]^ |
| | Capital efficiency | Scenario-based capital leverage, regenerative practice payback, DAO/community governance throughput, and capital-provider utility limits.^[35]^ |
| | Commons liberation | Time reclaimed, capital alignment, governance inclusion, pseudonymous participation boundaries, and land stewardship commitments.^[36]^ |
| | GNH alignment | Domain-level well-being, cultural preservation, renewable energy planning, vulnerable-group access, and foundational well-being signals.^[37]^ |
| | Regenerative outcomes | Impact summaries, community decision mechanisms, replication readiness, and adaptive management loops.^[38]^ |
| | Open-source scaling | Cost-per-farm economics, planned targets, adoption barriers, downside stress testing, and reusable open-source artifacts.^[39]^ |
| | Commons governance | Anti-capture policies, flexible redistribution, federation/mutual-aid protocols, algorithmic redistribution, and participatory signals.^[40]^ |
| **AI & Workflows** | Agent-assisted workflows | CIDS export, feedback synthesis, and report preparation with draft-only outputs. |
| | Stakeholder feedback | Private-by-default feedback with consent management and public-safe summaries. |

---

## 3. Problem Statement

Regenerative farms produce valuable ecological, social, and economic outcomes, but these outcomes are difficult to compare, verify, and communicate to partners, funders, and regulators. The challenges include:

### Evidence Fragmentation

Operational, financial, environmental, and social data live in spreadsheets, paper records, siloed apps, and informal knowledge. There is no single governed source that connects farm activities to impact outcomes.

### Impact Claim Governance

Impact claims are often made without structured evidence, maturity thresholds, or review workflows. Positive claims may overstate certainty, while negative findings and limitations go unreported.

### Carbon Claim Boundaries

Carbon-balance evidence from farm operations is easily confused with carbon credit issuance. Without clear boundaries, public carbon claims may imply external verification that has not occurred.

### Stakeholder Voice

Stakeholder feedback from workers, community members, buyers, and funders is rarely captured with consent management, privacy controls, or structured review. Public reports may include private feedback without explicit permission.

### Agent Limitations

AI agents can assist with data preparation, synthesis, and export, but they lack governance boundaries. Without clear rules, agents may verify or publish outputs without human review.

### Interoperability

Impact data needs to be shared with funders, regulators, and standards bodies in common formats. Without a compatibility layer like CIDS, each partnership requires custom integration.

Kokonut Intelligence addresses these challenges through governed data models, evidence maturity enforcement, consent-based privacy, agent safety constraints, and standards-compatible export.

---

## 4. System Architecture

### Technology Stack

| Layer | Technology | Role |
|-------|------------|------|
| Canonical core | PostgreSQL 16 + PostGIS 3.4 + Directus 12.1.1 | Schema, API, permissions, workflows, data entry UI |
| Analytics | ClickHouse 25.8 LTS | Time-series events and high-volume analytical queries |
| BI | Metabase 0.62.4 | Internal dashboards, aggregate reporting, custom visualizations, and MCP |
| Intelligence | Python 3.11 services | Metrics, forecasts, scoring, exports, ingestion, AI summaries, and ML anomaly detection |
| Verification | EAS on Celo + offchain evidence storage | Onchain attestations, offchain signed claims, MRV proof metadata |
| Governance and Guilds | Gnosis Moloch DAO + Colony metadata | Treasury governance, Guild contribution records, reputation snapshots |
| Contracts | Foundry + Solidity + OpenZeppelin | KokonutResolver attester gating for EAS schemas |
| Workflow orchestration | Prefect 3.x + durable scheduler | Pipelines, event-driven automations, leases, retries, and run history |
| External API | gRPC + Protobuf | Type-safe API, streaming, API-key authentication, and generated SDKs |

### Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                    INTERFACES                           │
│  Directus Studio │ Metabase │ API │ Agents             │
└────────┬────────┴─────┬─────┴──┬──┴────┬───────────────┘
         │              │        │       │
┌────────▼──────────────▼────────▼───────▼───────────────┐
│                    DIRECTUS                             │
│          REST API │ GraphQL │ SDK │ Flows              │
│          Permissions │ Automations │ Webhooks           │
└────────┬───────────────────────────────────────────────┘
         │
┌────────▼───────────────────────────────────────────────┐
│                 POSTGRESQL + POSTGIS                     │
│                                                         │
│  Master Data    Operational Facts    Financial Facts    │
│  ──────────     ────────────────     ──────────────    │
│  locations      farm_activity        financial_txn      │
│  farms          harvest_event        expense_event      │
│  plots          sales_event          crop_cost_alloc    │
│  crops          loss_event           noi_snapshot       │
│  crop_cycle     labor_event          cash_flow_snap     │
│  partners       field_note           value_flow_event   │
│  farm_registry  inventory_event      revenue_event      │
│                 maintenance_event                       │
│                                                         │
│  Environmental    Web3/Attestation    Modeled Outputs   │
│  ─────────────    ────────────────    ──────────────    │
│  soil_sample      wallet_profile      forecast_scenario  │
│  species_obs      attestation_record  forecast_output    │
│  remote_sensing   digital_lego_usage  metric_definition  │
│  weather_obs      attestation_schema  report_snapshot    │
│  sensor_reading   mrv_event           ai_summary         │
│  attestation_req  governance_event    agent_task         │
│  price_observation                    ingestion_log      │
│                                                         │
│  EBF Scoring (032-033)                                  │
│  ─────────────────────                                  │
│  ebf_pillar           ebf_scorecard                     │
│  ebf_rubric_band      ebf_score                         │
│  ebf_score_evidence   ebf_farm_metric_profile           │
│  ebf_calibration_*    ebf_trust_graph_*                 │
│  ebf_improvement_recommendation                         │
└────────┬───────────────────────────────────────────────┘
         │
┌────────▼───────────────────────────────────────────────┐
│              PYTHON INGESTION LAYER                     │
│                                                         │
│  weather.py / forecast.py → weather and climate APIs      │
│  rpc_indexer.py / DAO indexers → chain events             │
│  market_data.py / yahoo_finance.py → market prices        │
│  remote sensing / GEE / Copernicus → spatial evidence     │
│  sensors / MQTT / HTTP → telemetry and device events      │
│  eas_indexer.py → EAS attestations                        │
│                                                         │
│  All scripts: services/ingestion/                       │
│  Common framework: base.py (DB, logging, retry)         │
└────────┬───────────────────────────────────────────────┘
         │
┌────────▼───────────────────────────────────────────────┐
│                   CLICKHOUSE                            │
│                                                         │
│  events_raw │ wallet_events │ sensor_readings           │
│  weather_events │ financial_events │ dlego_events       │
│                                                         │
│  Materialized Views:                                     │
│  daily_event_counts │ hourly_sensor_stats               │
│  daily_wallet_activity │ monthly_financial_summary      │
│  daily_weather_summary │ daily_sensor_summary           │
│  sensor_reading_rate                                    │
└─────────────────────────────────────────────────────────┘
```

### API Layers

| Layer | Protocol | Auth | Use Case |
|-------|----------|------|----------|
| Directus REST | HTTP REST | Bearer token | CRUD, admin, integrations |
| Directus GraphQL | GraphQL | Bearer token | Complex queries, frontend |
| Directus SDK | JavaScript | Session | Application integration |
| ClickHouse HTTP | HTTP | Basic auth | Analytical queries |
| Directus MCP | MCP | Scoped token | AI agent access |
| Helper CLIs | Python modules | Local process auth | Registry validation, local CID prep, attestation request prep, agent manifest prep |

The optional Kokonut gateway is a separate FastAPI process, not part of the Directus API or base Caddy routing. Its protected routes accept gateway API keys or capability tokens according to route policy; Directus bearer authentication remains a separate boundary.

### Security Model

- **Roles:** Administrator, Field Worker, Supervisor, Manager, Finance, Analyst, Auditor, Agent Read-Only, Agent Write, Agent Full.
- **Policies:** Per-collection, per-action, per-field permissions enforced through Directus metadata, hooks, gateway policy, and service-level safety checks.
- **Field-level:** Sensitive fields hidden per role.
- **Row-level:** Filter rules restrict record visibility.
- **Audit:** All mutations logged to `audit_log`.
- **Evidence:** Raw evidence stored off-chain; hashes/CIDs on-chain.
- **Agent scope:** This repository stores agent metadata and tasks only; marketplace identity, payment, escrow, and reputation logic are external.^[1]^

### Schema Management

Schemas are version-controlled as SQL files in `schemas/postgres/`. Directus snapshots capture the API-layer state. ClickHouse schemas live in `schemas/clickhouse/`. Seed data lives in `schemas/seeds/`.

The repository currently contains 331 ordered PostgreSQL migrations, six ClickHouse schema files, and 117 seed files. Migration application is checksummed and fails closed on drift. The migration sequence, not this paper, is the authoritative source for exact database structure.

---

## 5. Data Lifecycle

Every important record follows a canonical four-state lifecycle:

```
draft → submitted → verified → published
```

- **Draft:** Record created; source payload preserved where available.
- **Submitted:** Mapped to Kokonut canonical schema and submitted for review.
- **Verified:** Reviewed, validated, linked to evidence.
- **Published:** Available to dashboards, APIs, attestations.

`rejected` is available for rework and exception paths. Payment, attestation, execution, and domain-specific states live in dedicated fields such as `payment_status`, `attestation_uid`, `attested_at`, `execution_status`, and `revocation_date`.^[2]^

Metric computation writes draft `metric_value` records; it does not verify them. Verification is a separate, explicit human action. Forecast execution similarly moves a scenario to `submitted`, not to `verified` or `published`.

### Time-Based Enforcement

- Stakeholder feedback requires a minimum **7-day review period** after submission before verification.^[3]^
- Metric proposals require a minimum **30-day discussion period** after proposal date before approval.^[4]^

### Role-Based Access

| Role | Access | Description |
|------|--------|-------------|
| Administrator | Full | Platform admin and all permissions |
| Field Worker | Create/read scoped records | Data entry; records start as `draft`; create permissions exclude lifecycle audit fields |
| Supervisor | Read all, submit | Submits records for review |
| Manager | Approve/verify operational records | Reviews and verifies governed operations |
| Finance | Finance approvals | Approves expenses, verifies sales, and approves revenue events |
| Analyst | Read verified/published | Read-only analysis over governed data |
| Auditor | Read all + audit log | Read-only access to all records and audit trails |
| Agent Read-Only | Read governed data | AI agents reading governed data for synthesis |
| Agent Write | Create drafts, submit/reject own | AI agents creating draft outputs with safety constraints |
| Agent Full | Agent-scoped write + task management | AI agents managing tasks within safety boundaries |

Directus hooks enforce review workflows for stakeholder feedback, stakeholder outcomes, impact claims, metric proposals, agent tasks, AI summaries, and agent action logs.^[5]^

---

## 6. Evidence Maturity Model

Kokonut uses a 0-6 evidence maturity model across impact claims, MRV claims, stakeholder feedback, and public reporting.^[6]^

| Level | Key | Public Claim | Meaning |
|---:|---|---|---|
| 0 | `narrative_only` | No | Narrative without structured evidence. |
| 1 | `self_reported` | No | Self-reported observation or feedback. |
| 2 | `structured_record` | No | Structured record with required fields. |
| 3 | `reviewed_record` | No | Human-reviewed record. |
| 4 | `evidence_linked` | Yes | Reviewed record with CIDs, hashes, or evidence URLs. |
| 5 | `attested_record` | Yes | Evidence-linked record with attestation. |
| 6 | `externally_verified` | Yes | Externally verified record with methodology and verifier reference. |

### Public Claim Eligibility

- Levels 0-3 are internal or pre-publication evidence states.
- Level 4 is the minimum maturity for ordinary public impact claims.
- Level 5 records may include onchain/offchain attestations, but still need reviewer interpretation.
- Level 6 is required when a public carbon claim could be read as externally verified.

### Public Carbon Claims

Public carbon claims require Level 6. Level 5 EAS attestation proves a claim was attested, but does not equal external verification. The following fields are required for public carbon claims:

- `claim_category = 'carbon'`
- `claim_type = 'third_party_verified_claim'`
- `evidence_maturity = 6`
- Non-empty `external_verifier`
- Non-empty `methodology_ref`
- `status = 'published'`

### Enforcement Locations

Evidence maturity is enforced or surfaced in:

- `mrv_claim`
- `impact_claim`
- `stakeholder_feedback`
- `stakeholder_outcome`
- Public-safe views (`v_public_metric_summary`, `v_public_attestation_summary`, `v_public_ebf_scorecard`, `v_public_ebf_scorecard_summary`, `v_public_ebf_pillar_summary`)
- Report snapshots (`report_snapshot.public_interest_summary`)
- CIDS export
- Directus workflow hooks

### Agent Use

Agents may summarize evidence maturity and identify gaps. They cannot raise maturity, verify records, or publish claims. Any agent-produced summary is a draft input for human review.^[7]^

### EBF Scorecards

EBF public scorecards require evidence maturity >= 4 for ordinary pillar scores. Public carbon pillar scores require:

- Evidence maturity = 6
- A linked published `impact_claim` with `claim_category = 'carbon'` and `claim_type = 'third_party_verified_claim'`
- Non-empty `external_verifier` and `methodology_ref`
- `status = 'published'`

EBF score publication is gated by `services/scoring/gates.py`, which checks evidence maturity, claim linkage, and registry backing before allowing public exposure.^[29]^

---

## 7. CIDS Mapping and Export

Kokonut targets Common Impact Data Standard (CIDS) v3.2.0 Essential Tier. PostgreSQL/Directus remains the canonical data layer; CIDS is an export compatibility layer.^[8]^

### Mapping

| Kokonut Source | CIDS Class | Notes |
|---|---|---|
| `location`, `farm` | `cids:Organization` | Uses farm/location name, description, and stable URI. |
| `farm_registry_record` | `cids:Program` | Represents the farm program/project profile. |
| `stakeholder_outcome` | `cids:Outcome`, `cids:StakeholderOutcome` | Connects outcome, stakeholder group, importance, and theme. |
| `stakeholder_feedback` | `cids:Stakeholder` support data | Private by default; public export uses summaries only. |
| `metric_definition` | `cids:Indicator` | Governed metric definition. |
| `metric_value` | `cids:IndicatorReport` | Verified metric values only. |
| `ebf_score` | `cids:IndicatorReport` | EBF pillar scores with `kokonut:ebfPillar` and `kokonut:cidsMapping` metadata.^[29]^ |
| `impact_claim` | `cids:ImpactReport` | Includes maturity, methodology, verifier, and attestation metadata. |
| `sdg` / `farm_impact_mapping` | `cids:Theme` | SDG theme URI uses `https://metadata.un.org/sdg/{number}`. |

### Essential Tier Classes

The current exporter emits these CIDS-compatible classes when source data exists:

- `cids:Organization`
- `cids:Program`
- `cids:ImpactPathway`
- `cids:Stakeholder`
- `cids:StakeholderOutcome`
- `cids:Outcome`
- `cids:Indicator`
- `cids:IndicatorReport`
- `cids:ImpactReport`
- `cids:Theme`

### Export Commands

```bash
# Export CIDS Essential Tier JSON-LD for a location
python3 -m services.registry.cids_export --location-id UUID

# Agent-assisted CIDS export (read-only)
python3 -m services.agents.cids_agent --location-id UUID --summary
```

### Governance Boundary

CIDS export does not create or publish canonical records. Directus/PostgreSQL lifecycle state, evidence maturity, consent fields, and public-safe views determine what may appear in partner-facing outputs.

### Compatibility Notes

- Public carbon claims require Evidence Maturity Level 6 before export as public claims.
- Private stakeholder feedback is not exported as public feedback.
- CIDS export is a compatibility layer; PostgreSQL/Directus remains canonical.

---

## 8. Stakeholder Feedback

Stakeholder feedback is private by default. Public Green Paper outputs can include only consented summaries and aggregate review signals.^[9]^

### Records

| Table | Purpose |
|---|---|
| `stakeholder_feedback` | Raw or summarized stakeholder feedback with consent, sentiment, themes, and maturity |
| `stakeholder_feedback_review` | Review, escalation, response, and publication trail |
| `v_public_stakeholder_feedback_summary` | Public-safe feedback summaries only |

### Public Exposure Rules

Public feedback requires all of the following:

- `consent_given = TRUE`
- `consent_scope` is `public_summary`, `public_quote`, or `public_full`
- `status = 'published'`
- `public_summary` is non-empty

Raw private feedback should not be included in public reports, CIDS exports, dashboards, or agent outputs.

### Review Workflow

Use `draft`, `submitted`, `verified`, `published`, and `rejected` for feedback lifecycle. Rejected feedback is retained for internal governance but excluded from public dashboards and summaries.

Feedback requires a minimum **7-day review period** after submission before verification. This is enforced in the Directus workflow hook.^[10]^

### Agent Synthesis

`services.agents.feedback_agent` summarizes public feedback and aggregates private/no-consent counts. With `--store`, it creates a draft `ai_summary` for human review.^[11]^

```bash
python3 -m services.agents.feedback_agent --location-id UUID
python3 -m services.agents.feedback_agent --location-id UUID --store
```

### Holistic Well-being And Cultural Context

Grant-review feedback highlighted that Kokonut's cultural heritage, local-language accessibility, participatory governance, and holistic well-being evidence should be explicit rather than implied. The Green Paper now treats these as governed public-safe evidence objects.^[33]^

| Record | Purpose |
|---|---|
| `cultural_context_record` | Local-language needs, traditional knowledge boundaries, heritage species, community stories, and land-memory context |
| `wellbeing_metric_observation` | Operator capability, community trust, worker safety, training access, benefit transparency, and cultural-capital observations |
| `participatory_action_record` | Traceability from stakeholder feedback to metric proposals, report changes, governance review, or operator actions |

Public cultural context requires explicit consent, public scope, published status, and a non-empty public summary. Raw cultural knowledge, household-level observations, and non-consented feedback remain private.

---

## 9. Impact Claims and Metric Proposals

### Impact Claims

Impact claims are governed records that connect farm outcomes to evidence, maturity levels, and verification metadata.^[12]^

**Public Claim Requirements:**

- Evidence maturity >= 4 for ordinary public claims.
- Evidence maturity = 6 for public carbon claims (with external verifier and methodology reference).
- `status = 'published'` for public exposure.

**Claim Validation:**

Directus hooks validate public claims at creation and update time:

- Public claims must have evidence maturity >= 4.
- Carbon claims must have `claim_type = 'third_party_verified_claim'`.
- Carbon claims must have non-empty `external_verifier` and `methodology_ref`.
- Level 6 is enforced for public carbon claims.^[13]^

### Participatory Metric Proposals

Participatory metrics let farm operators, workers, advisors, and DAO reviewers propose measurements that are useful locally before they become governed platform metrics.^[14]^

**Workflow:**

```
proposed → discussed → approved → implemented → deprecated
proposed → rejected
rejected → proposed
```

**Required Review Questions:**

- Who proposed the metric and why?
- Which stakeholder groups will use the metric?
- What data source and collection method are feasible?
- How often should it be collected?
- What decision will it support?

**Implementation:**

When a proposal reaches `implemented`, it must link to `metric_definition_id`. The Directus hook enforces transition rules and stamps reviewer metadata. Proposals require a minimum **30-day discussion period** after proposal date before approval.^[15]^

---

## 10. Agent Safety and Workflows

Kokonut agents assist with drafts, exports, synthesis, and review preparation. They do not replace human governance.^[16]^

### Rules

- Agents can create draft outputs.
- Agents can submit or reject their own outputs where hooks allow it.
- Agents cannot verify or publish their own outputs.
- High-risk actions require human approval and audit logging.

### High-Risk Actions

The following actions are flagged as high-risk and require human approval:

- `publish`
- `attest`
- `onchain_submit`
- `delete`
- `bulk_update`
- `financial_write`
- `status_change_to_published`

### Enforcement Layers

- Database constraints in `schemas/postgres/029_impact_accountability_foundation.sql`.
- Directus hook rules in `extensions/kokonut-hooks/src/agent-safety.ts`.
- Python preflight helpers in `services/agents/safety.py`.
- Audit log flags in `agent_action_log.high_risk` and `agent_action_log.requires_human_approval`.

### Task Catalogue

| Task | Purpose | Writes | Risk |
|---|---|---|---|
| `cids_export` | Prepare CIDS v3.2.0 Essential Tier JSON-LD for a location | None | Low |
| `feedback_synthesis` | Summarize public stakeholder feedback and aggregate private/no-consent signals | Optional `ai_summary:draft` | Medium |
| `public_interest_report_context` | Prepare limitations, evidence gaps, and public stakeholder voice for reports | None | Low |
| `ebf_scorecard_draft` | Draft EBF scorecard from farm metric profiles, rubric bands, and evidence links | Draft `ebf_scorecard` + `ebf_score` rows | Medium |
| `ebf_evidence_gap` | Identify evidence gaps between current farm metrics and EBF rubric requirements | Read-only report | Low |
| `ebf_calibration_memo` | Draft calibration memo from trust graph and rubric decisions | Draft calibration report | Low |
| `ai_summary_synthesis` | Generate structured AI summaries from governed data for human review | Optional `ai_summary:draft` | Medium |
| `holistic_wellbeing_synthesis` | Summarize cultural context, well-being observations, and participatory actions | Optional `ai_summary:draft` | Medium |
| `financial_resilience_synthesis` | Summarize financial sustainability, risk mitigation, and scaling roadmap evidence | Optional `ai_summary:draft` | Medium |
| `capital_efficiency_synthesis` | Summarize capital efficiency, governance throughput, and capital-provider utility evidence | Optional `ai_summary:draft` | Medium |
| `commons_liberation_synthesis` | Summarize time liberation, capital alignment, governance inclusion, and land stewardship evidence | Optional `ai_summary:draft` | Medium |
| `gnh_alignment_synthesis` | Summarize GNH alignment, cultural preservation, renewable energy, and vulnerable access evidence | Optional `ai_summary:draft` | Medium |
| `regenerator_synthesis` | Summarize regenerative outcomes, community governance, replication readiness, and adaptive stewardship | Optional `ai_summary:draft` | Medium |
| `open_source_capitalist_synthesis` | Summarize scaling economics, adoption barriers, stress tests, and open-source artifacts | Optional `ai_summary:draft` | Medium |
| `kokonut_commons_synthesis` | Summarize anti-capture governance, redistribution, federation, and participatory signals | Optional `ai_summary:draft` | Medium |

### Commands

```bash
python3 -m services.agents.tasks --list
python3 -m services.agents.tasks --describe cids_export
python3 -m services.agents.cids_agent --location-id UUID --summary
python3 -m services.agents.feedback_agent --location-id UUID
python3 -m services.agents.feedback_agent --location-id UUID --store
python3 -m services.agents.ebf_scorecard_agent --location-id UUID --draft
python3 -m services.agents.ebf_evidence_gap_agent --location-id UUID
python3 -m services.agents.ebf_calibration_agent --location-id UUID --draft
```

### Reviewer Responsibility

Reviewers may use agent outputs as evidence preparation, but final publication, attestation submission, and public claims remain human-approved decisions.

---

## 11. Web3 Verification

Celo is the primary chain for Kokonut attestations. EAS v1.3.0 is deployed on Celo mainnet, and `KokonutResolver` gates attestation to allowed attesters under Kokonut multisig ownership.^[17]^

### Deployed Contracts

| Contract | Address |
|----------|---------|
| EAS | `0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92` |
| SchemaRegistry | `0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34` |
| KokonutResolver | `0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad` |

### Registered Schemas

| Schema | UID | Use Case |
|--------|-----|----------|
| `kokonut-mrv` | `0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54` | MRV claims |
| `kokonut-impact` | `0xb99bb4b2a55218b8f4df1f0bd4c39400711809f13ef5d150d2903648c6590dfe` | Environmental impact |
| `kokonut-financial` | `0x75b42beb85dd852134dfaff3de41b8dc361ed0cb2bf93ce3009c8ec082de905b` | Financial summaries |
| `kokonut-harvest` | `0xb359f9756e3cb3597e4048dccae2842083359906fbae8dc8c0e9af8ac1b3ccff` | Harvest verification |
| `kokonut-compliance` | `0x59632edcf1d04be0c2dcfd572282bbd4dac518e7a92872ec45ade29876ef95f5` | Partner compliance |

### Attester Wallets

- Deployer: `0x3394C45b5938127EB56603A6051dF26CFAF08C26`
- Kokonut multisig: `0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5`

### Resolver Ownership

Resolver ownership is transferred to the Kokonut multisig. The resolver gates attestation to allowed attesters only.

### Private Evidence Strategy

- Public EAS metadata stores hashes, CIDs, UIDs, chain labels, transaction hashes, and timestamps.
- Raw private MRV payloads remain in controlled off-chain storage.
- Public attestation summaries join `attestation_record` to `location` through `subject_type = 'location'` and `subject_id`.
- Public attestation summaries are scoped to Celo.^[18]^

### CLI Commands

```bash
python3 -m services.attestation.cli info --chain celo
python3 -m services.attestation.cli schema list
python3 -m services.attestation.cli query --uid 0xATTESTATION_UID --chain celo
```

### Chain Expansion

New chains get testnet-first deployments. EAS chain config lives in `services/attestation/config.py` and `services/ingestion/config.py`.

---

## 12. Carbon and Environmental Impact

Kokonut tracks carbon sequestration, greenhouse gas emissions, biodiversity, and regenerative practice scoring across farm operations.^[19]^

### Carbon Framework Tables

| Table | Purpose |
|---|---|
| `ghg_emission_factor` | IPCC-based reference emission factors (fuel, fertilizer, pesticide, transport, machinery, electricity) with regional overrides |
| `ghg_emissions_inventory` | Transport, machinery, and input emissions tracking with CO2e computed from emission factors |
| `tree_inventory` | Above-ground carbon via allometric model (tree count, height, DBH → biomass → carbon → CO2e) |
| `underplanting_event` | Companion species planting records with survival tracking |
| `carbon_benchmark` | Tree system carbon benchmarks (coconut, oil palm, mango, cacao, mixed agroforestry, native forest) |
| `regenerative_practice_checklist` | Scored 0-5 per-principle assessment across 5 Principles of Regeneration |
| `framework_phase` | Framework implementation phase tracking (baseline → monitoring → verified → published) |
| `climate_impact_summary` | Annual climate-impact summary with sequestration, emissions, biodiversity, and regenerative score |
| `operations_protocol` | Versioned handbook sections for soil management, biodiversity, emissions tracking, data entry, and reporting |

### Analytics

```bash
# Carbon balance (sequestration vs emissions)
python3 -m services.analytics --carbon-balance --location-id UUID

# GHG emissions by category
python3 -m services.analytics --ghg-emissions --location-id UUID

# Tree carbon from inventory
python3 -m services.analytics --tree-carbon --location-id UUID

# Regenerative practice score
python3 -m services.analytics --regenerative-score --location-id UUID

# Emission factors reference
python3 -m services.analytics --emission-factors

# Carbon benchmarks
python3 -m services.analytics --carbon-benchmarks
```

### Carbon Balance

The carbon balance view computes net carbon position by comparing sequestration (from tree inventory and soil organic matter changes) against emissions (from fuel, fertilizer, transport, and machinery). The net position is classified as net_negative, neutral, or net_positive.

### Regenerative Score

The regenerative practice checklist scores farms across 5 Principles of Regeneration:

1. Care for soil
2. Increase biodiversity
3. Minimize external inputs
4. Close loops
5. Empower community

Each principle is scored 0-5, and the total regenerative score provides a single-number assessment of farm practices.

### EBF Pillar Scoring

The Ecological Benefits Framework (EBF) provides multi-dimensional farm evaluation across 7 pillars, each scored against a 10-band rubric (0-9).^[29]^

| Pillar | Focus |
|--------|-------|
| Air Quality | Emissions, dust, air quality management |
| Water Management | Water use efficiency, runoff, irrigation |
| Soil Health | Organic matter, erosion, soil biology |
| Biodiversity | Species diversity, habitat, ecological connectivity |
| Carbon Sequestration | Tree carbon, soil carbon, net carbon balance |
| Equity & Community | Labor practices, community engagement, fair access |
| Implementation Quality | Practice adoption, monitoring, adaptive management |

**Scoring Model:**

- Each pillar is scored against rubric bands defined in `ebf_rubric_band`.
- Scores are normalized to 0-100 using `services/scoring/normalization.py`.
- Confidence is computed from source data completeness, review status, and evidence linkage via `services/scoring/confidence.py`.
- Public scorecards require evidence maturity >= 4 and published status.
- Public carbon pillar scores additionally require Level 6 with a linked published third-party verified `impact_claim`.

**Trust Graph and Provenance:**

EBF scores carry provenance through `ebf_trust_graph_node` and `ebf_trust_graph_edge` tables, recording which sources, calibration decisions, and rubric mappings contributed to each score. Trust graph exports are available in JSON and Mermaid formats.^[31]^

**Calibration:**

Rubric calibration ensures consistent scoring across farms and reviewers. Calibration sessions are recorded in `ebf_calibration_session` with decisions in `ebf_calibration_decision`. Third-party calibration is preferred; team calibration requires a report URL or hash before verification or publication. Calibration frequency is annual for network farms and semi-annual for pilot farms.^[32]^

**Portfolio Comparison:**

EBF portfolio evaluation uses a messy roll-up approach, aggregating pillar scores by confidence and maturity without ranking farms as interchangeable units. Portfolio summaries are available via `services/analytics/portfolio.py` and the `--ebf-portfolio-summary` CLI command.^[30]^

```bash
# EBF scorecard CLI
python3 -m services.scoring --location-id UUID

# EBF portfolio summary
python3 -m services.analytics --ebf-portfolio-summary
```

### Carbon Disclaimer

Carbon-balance evidence is distinct from carbon credit issuance. The platform implements governed internal records for credit classes, verified-batch issuance by authorized issuers, balances, custody, marketplace activity, bridging, and retirement. Those ledger events do not by themselves create recognition by an external registry or replace independent certification. Public carbon claims require Evidence Maturity Level 6, external verifier text, methodology reference, and published status. EAS attestations provide verification metadata but do not replace external verification.^[20]^

---

## 13. Additional Evidence Modules

The platform includes seven additional governed evidence modules beyond the core operations, EBF scoring, holistic well-being, and financial resilience layers. Each module has dedicated schema tables, public-safe views, seeded metric definitions, a synthesis agent, report types, and an operating guide.^[35-41]^

### Capital Efficiency and Utility

Records scenario-based capital leverage, regenerative practice payback periods, governance throughput (proposals, voting, execution), and capital-provider utility evidence. Public-safe views expose aggregate efficiency signals with explicit limitations — capital efficiency reports are planning evidence, not guarantees of returns.

| Record | Purpose |
|---|---|
| `capital_efficiency_scenario` | Capital deployment, leverage ratio, expected vs actual outcome |
| `regenerative_efficiency_observation` | Practice payback period, cost savings, ecological return |
| `governance_throughput_observation` | Proposal volume, voting participation, execution rate |
| `capital_provider_utility_scenario` | Provider satisfaction, risk-adjusted return, redeployment intent |

Report types: `capital_efficiency`, `governance_throughput`, `capital_provider_utility`. Agent: `capital_efficiency_agent`. Guide: [capital-efficiency.md](capital-efficiency.md).^[35]^

### Commons Liberation and Stewardship

Records time reclaimed from extractive labor, capital alignment with regenerative principles, governance inclusion across stakeholder groups, and land stewardship commitments. Public-safe views expose aggregate liberation signals with privacy boundaries — pseudonymous participation is supported, and household-level observations remain private. Land stewardship records are commitment evidence, not legal land-transfer or landlord-abolition claims.

| Record | Purpose |
|---|---|
| `time_liberation_observation` | Hours reclaimed, activity shifted, voluntary vs obligation labor |
| `capital_alignment_assessment` | Capital source alignment with regenerative principles, extraction risk |
| `governance_inclusion_observation` | Participation by group, decision influence, barrier removal |
| `land_stewardship_commitment` | Stewardship area, tenure security, biodiversity commitment, community access |

Report types: `time_liberation`, `capital_alignment`, `governance_inclusion`, `land_stewardship`. Agent: `commons_agent`. Guide: [commons-liberation.md](commons-liberation.md).^[36]^

### GNH Alignment and Inclusion

Records Gross National Happiness domain-level alignment, cultural preservation plans, renewable energy planning (distinguishing planned from implemented), vulnerable-group access evidence, and foundational well-being observations. GNH alignment is evidence of well-being signals, not Bhutan-readiness certification. Renewable energy records distinguish `planned` from `implemented` status.

| Record | Purpose |
|---|---|
| `gnh_alignment_assessment` | GNH domain scores (psychological, health, education, cultural, time, ecological, living, governance) |
| `cultural_preservation_plan` | Language preservation, traditional practice, heritage asset protection |
| `renewable_energy_plan` | Energy source, capacity, status (planned vs implemented), displacement calculation |
| `vulnerable_group_access_plan` | Group identification (privacy-protected), access barrier, mitigation, outcome |
| `foundational_wellbeing_observation` | Food security, housing, water access, energy access, education access observations |

Report types: `gnh_alignment`, `cultural_preservation`, `renewable_energy`, `vulnerable_access`, `foundational_wellbeing`. Agent: `gnh_agent`. Guide: [gnh-alignment.md](gnh-alignment.md).^[37]^

### Regenerative Outcomes and Stewardship

Records concise grant-facing outcome summaries, community governance decision mechanisms, replication readiness assessments, and adaptive stewardship review loops. Replication readiness is a checkpoint signal, not a commitment to launch new farms. Outcome summaries are evidence for grant reporting, not performance guarantees.

| Record | Purpose |
|---|---|
| `regenerative_outcome_summary` | Outcome area, indicator, baseline, current, direction, evidence links |
| `community_governance_mechanism` | Decision mechanism, participation scope, binding vs advisory, outcome |
| `replication_readiness_assessment` | Readiness dimension, score, evidence, blocker, mitigation |
| `adaptive_stewardship_review` | Review cycle, observation, adjustment, rationale, next review date |

Report types: `regenerative_outcomes`, `community_governance`, `replication_readiness`, `adaptive_stewardship`. Agent: `regenerator_agent`. Guide: [regenerative-outcomes.md](regenerative-outcomes.md).^[38]^

### Open Source Capitalist Scaling

Records farm launch unit economics, network scaling targets, adoption barrier assessments, perpetual value stress tests, and reusable open-source artifact evidence. Scaling targets are explicit planned numbers, not unlimited-scaling claims. Stress tests model downside scenarios including funding cuts, key-person loss, and adoption failure.

| Record | Purpose |
|---|---|
| `farm_launch_unit_economics` | Cost per farm, revenue ramp, break-even, capital efficiency |
| `network_scaling_target` | Target region, planned farm count, timeline, capital needed, dependencies |
| `adoption_barrier_assessment` | Barrier category, severity, affected stakeholders, mitigation, status |
| `perpetual_value_stress_test` | Scenario, shock type, impact, recovery path, residual risk |
| `open_source_impact_artifact` | Artifact type, license, reuse count, derivative works, community contribution |

Report types: `scaling_economics`, `adoption_barriers`, `perpetual_value_stress`, `open_source_impact`. Agent: `open_source_capitalist_agent`. Guide: [open-source-capitalist-scaling.md](open-source-capitalist-scaling.md).^[39]^

### Kokonut Commons Governance

Records anti-capture governance policies, flexible redistribution policies, federation/mutual-aid protocols, algorithmic redistribution mechanisms, and participatory signal experiments. Redistribution policies are flexible per scenario — no single allocation percentage is hardcoded across all contexts. Participatory signal experiments (meme/vibes) are advisory only unless `decision_binding` states otherwise and human review approves use.

| Record | Purpose |
|---|---|
| `anti_capture_policy` | Policy type, rule, enforcement mechanism, review cadence, violation response |
| `redistribution_policy` | Scenario, allocation, recipient pool, mechanism, review status |
| `federation_protocol` | Protocol type, partner, terms, mutual aid scope, governance alignment |
| `algorithmic_redistribution_mechanism` | Algorithm, input signals, output allocation, audit trail, override |
| `participatory_signal_experiment` | Signal type, source, weight, advisory vs binding, review status |

Report types: `anti_capture_governance`, `redistribution_policy`, `federation_mutual_aid`, `algorithmic_redistribution`, `participatory_signal`. Agent: `kokonut_commons_agent`. Guide: [kokonut-commons-governance.md](kokonut-commons-governance.md).^[40]^

### Bio Factory Operations

Records bio-organic fertilizer production batches, ingredient provenance, recipe knowledge, distribution, quality testing, ingredient composition reference (20 seeded ingredients with typical NPK ranges), and LAC regional input availability (8 Caribbean/Central/South America entries). Recipes are public knowledge for adaptation, not commercial endorsements. Quality test results are advisory, not certification. Sargassum and other marine materials require washing (3-5 rinses) to reduce salts and arsenic before use.

| Record | Purpose |
|---|---|
| `bio_factory_batch` | Production batch: type, method, inputs, outputs, conditions, microbial strain |
| `bio_input_provenance` | Ingredient sourcing: supplier, origin, organic certification, NPK, quality warnings |
| `bio_recipe_library` | Recipe knowledge base: ingredients, ratios, process steps, fermentation conditions |
| `bio_factory_distribution` | Distribution tracking: recipient type, quantity, region, application purpose |
| `bio_factory_quality_test` | Quality test results: NPK, pH, microbial count, pass/fail, lab accreditation |
| `bio_ingredient_composition_reference` | Composition matrix: typical NPK ranges for 20 ingredients |
| `bio_regional_input_availability` | LAC regional inputs: region, seasonality, cautions, quality considerations |

Report types: `bio_factory_batch`, `bio_input_provenance`, `bio_recipe_library`, `bio_quality_test`, `bio_regional_input`. Agent: `bio_factory_agent`. Guide: [bio-factory-operations.md](bio-factory-operations.md).^[41]^

---

## 13A. Operational Intelligence and Decisioning

The platform implements a governed Observe-Orient-Decide-Act-Feedback (OODA) loop. It is an evidence-to-decision system, not an autonomous decision-maker.

| Phase | Implemented capabilities | Main records or services |
|---|---|---|
| Observe | Sensors, MQTT/HTTP ingestion, weather and climate data, remote sensing, freshness checks, anomaly detection | `services/ingestion/`, `services/stream/`, `sensor_reading`, `ingestion_log` |
| Orient | Situation assessment, CRISP risk, trends, threat intelligence, geostatistics, systems thinking | `services/orientation/`, `services/crisp/`, `services/trends/`, `services/threatcasting/` |
| Decide | Policy evaluation, Delphi recommendations, path comparison, advisory recommendations | `services/decision/`, `services/delphi/`, `services/analytics/advisor.py` |
| Act | Governed work items, alerts, data-stream posts, approved actuator commands, field workflows | `services/management/`, `services/data_stream/`, `services/ingestion/mqtt_actuator.py` |
| Feedback | Action outcomes, adaptive thresholds, sampling changes, learning-rate and cycle-time measurements | `services/feedback/`, `services/systems/`, `services/orientation/cycle_tracker.py` |

The `situation_assessment`, `decision_policy`, `decision_log`, `action_outcome`, `feedback_loop`, `adaptive_threshold`, and `ooda_cycle_log` records preserve the decision trail. Seeded policies require approval, and feedback automation supports dry-run and proposal-oriented operation.

### CRISP Risk Scoring

CRISP is the platform's configurable internal risk intelligence engine. It scores carbon yield, climate, policy, financial viability, and implementation risk on a 0-100 scale, where higher values indicate higher risk. Default weights are 0.40, 0.25, 0.15, 0.10, and 0.10 respectively; locations may have approved weight overrides. Composite bands are AAA, AA, A, B, C, and D.

CRISP assessments are planning and risk evidence. They are not credit ratings, insurance decisions, external certification, or guarantees of project performance. The implementation lives in `services/crisp/` and migration `076_crisp_risk_scoring.sql`.

### Threatcasting, Backcasting, and Delphi

Threatcasting records climate, market, policy, ecological, social, health, security, and technology threats. Warning flags, incoming signals, cross-impact relationships, narratives, horizons, cascades, and intelligence briefings support forward-looking analysis. Backcasting works from a future state through milestones, sustainability principles, assumption challenges, pathway comparisons, and premortems.

The real-time Delphi module supports pseudonymous panels, continuously updated evaluations, weighted median/IQR/CV summaries, consensus snapshots, minority views, and draft recommendations. Facilitator outputs require human approval. These tools are advisory and cannot publish claims, execute funds, or alter stakeholder decisions autonomously.

Primary records are defined in `159_threatcasting.sql` and `161_delphi.sql`. Representative commands include:

```bash
python3 -m services.threatcasting intelligence --location-id UUID
python3 -m services.threatcasting preempt --location-id UUID
python3 -m services.threatcasting create-backcast --narrative-id UUID --location-id UUID --name "Plan" --future-state "..." --gaps "..."
python3 -m services.delphi live-summary --study-id UUID
python3 -m services.agents.delphi_facilitator_agent --study-id UUID --draft
```

### Systems Thinking, Trends, and Spatial Analysis

The systems toolkit provides causal-loop and leverage analysis, archetype detection, delay mapping, double-loop learning, stock-flow models, mental-model comparison, growth-curve analysis, adaptation velocity, improvement-rate tracking, meta-learning, and statistical process control. It is used to expose assumptions, delays, feedback effects, and possible intervention points.

Trend services provide least-squares estimates, Mann-Kendall significance, exponential smoothing, seasonal decomposition, change-point detection, forecasts, and forecast-accuracy tracking. Geostatistics provides variograms, kriging, simulation, spatial autocorrelation, spatial cross-validation, and sensor-design analysis. These outputs support soil-carbon prediction, situation assessment, and reports; they do not turn modeled results into verified evidence.

## 13B. Precision Agriculture and Ecological Modeling

The platform contains a field-operations layer beyond the core farm ledger:

- Weather forecasts, FAO-56 evapotranspiration, crop coefficients, water balance, and spray-window analysis.
- Crop growing-degree-day accumulation, stage detection, projected stages, and anomaly tracking.
- Precision irrigation zones, moisture targets, ETc-based schedules, rule evaluation, water efficiency, and approval gates.
- Prescription maps with natural-break and equal-interval classification for fertilizer, irrigation, and seed inputs.
- Nutrient budgets for inputs, soil tests, crop removal, recommendations, and efficiency.
- Pest scouting, economic thresholds, IPM interventions, pesticide safety intervals, resistance, degree-day, trap monitoring, and organic-pest scoring.
- Yield recording, trend and benchmark analysis, ensemble yield prediction, and harvest summaries.
- Digital twins with crop growth, water, nitrogen, biomass, carbon, scenarios, comparison, and Monte Carlo wrappers.
- Equipment usage, maintenance, OEE, operating cost, and cooperative asset utilization.
- Mobile offline queues, conflict resolution, sync audits, LLM chat intent handling, farmer identity, training, and cooperative workflows.

Environmental and ecological services add soil-organic-carbon prediction, spectral and time-series features, ecological models, trophic analysis, energy monitoring, waste and composting records, landscape and habitat conservation, pollinator health, tree tracking, and organic-certification readiness. Organic readiness is a 0-100 assessment across transition, soil, inputs, pests, biodiversity, buffers, records, training, and harvest segregation; it is not a certification.

The principal implementations are under `services/analytics/`, `services/ingestion/`, `services/geostatistics/`, and migrations `134` through `157`. Forecasts and ecological models remain projections until governed review and evidence requirements are satisfied.

## 13C. Financial, Credit, and Market Infrastructure

The financial layer includes governed revenue, expense, sales, cash-flow, and value-flow records; standard financial statements; IRR, NPV, MIRR, ROI, and payback calculations; true-cost accounting; natural and social capital valuation; life-cycle assessment; GRI mapping; and cross-capital flow analysis.

Business services include revenue streams, pricing, cost structures, break-even and sensitivity analysis, Business Model Canvas generation, business plans, pitch decks, SWOT/TOWS, PESTEL, publics and market segmentation, partner lifecycle, channel orchestration, traceability, digital finance, and marketplace workflows. These are decision-support and planning outputs, not funding or revenue guarantees.

Additional platform surfaces include Fortune 500-style comparative scoring with explicit benchmark context, the ten-dimension revenue-multiplier analyzer, Abundance Protocol impact-estimate and validation records, and token-reward calibration diagnostics. These outputs are signals for review, not rankings that make farms interchangeable or automatic compensation claims.

### Credit and Ecocredit Records

The internal credit module models a class-to-batch-to-balance-to-retirement hierarchy. It supports project enrollment, batch issuance by authorized issuers, account and batch custody, baskets, marketplace orders, fees, cross-chain bridge records, and retirement certificates. Carbon-credit adjustment and retirement-integrity controls preserve supply, custody, and independent human confirmation boundaries.

These records are internal platform ledgers. They do not establish external registry issuance, certification, or recognition. External writes and marketplace identity, payment, escrow, and reputation logic remain outside the scope of this repository where stated in the agent and platform boundaries.

Representative commands:

```bash
python3 -m services.credit_class.cli class list --type carbon
python3 -m services.credit_class.cli batch balance --batch-id UUID
python3 -m services.credit_class.cli marketplace sell --batch-id UUID --seller 0x1234 --quantity 100 --price 2500 --denom cusd
python3 -m services.analytics.carbon_credits --confirm-retirement --retirement-id UUID --reviewer-id REVIEWER_UUID
```

## 13D. Strategy, Planning, and Process Management

Strategy services model vision and mission, capability maps and maturity, strategy maps, objectives, initiatives, KPIs, strategy choices and assumptions, execution snapshots, coherence, contingencies, risk evidence, foresight, consultation, communication, competitive landscape, strategic positioning, advantage assessment, and technology roadmaps. `services/strategy_markup/` exports a deterministic StratML Part 1 projection; PostgreSQL remains canonical.

Planning services provide approved budgets and lines, variance analysis, objectives and KPI reviews, program/project portfolios, capacity-aware planning, and an S&OP cockpit. They organize work without claiming that a plan has been executed.

### Business Process Management

`services/workflow_specs/` defines state machines for governed entities, including work items, budgets, objectives, projects, data-stream posts, claims, reports, stakeholder records, market orders, pest interventions, emergency incidents, and coordination. The process-model synchronization layer mirrors specifications in the database.

Process mining discovers variants and case timelines; conformance checks compare observed paths with specifications; predictive BPM estimates SLA breach risk; process control provides statistical process-control charts and CTQ analysis; process health and escalation services expose overdue or degraded flows. Work-item management adds assignments, responsibility, self-selection modes, SLA breaches, learning plans, and escalation. These are operational governance controls, not autonomous workforce management.

Innovation services provide a human-approved stage-gate lifecycle from discovery and framing through experimentation, validation, investment readiness, funding, piloting, adoption, scaling, and retirement. Gate evaluations and transition logs preserve the evidence trail.

## 13E. Identity, Linked Data, and Federation

The platform's identity and semantic layers make governed records addressable and exportable:

- The IRI service generates deterministic `kokonut:{entity_type}:{entity_id}:v{version}` identifiers, version history, and content hashes.
- RDF graph building projects governed records into `rdf_triple`; a constrained SPARQL-to-SQL engine supports basic graph patterns.
- JSON-LD and LinkML services provide schema validation and machine-readable metadata.
- The Metadata Graph API resolves IRIs and serves linked metadata.
- The evidence-lineage projection builds audience-aware nodes and edges from registries, metric definitions and values, claims, attestations, and schemas. Rebuilds are atomic and validate graph integrity.
- The governed Data Stream stores posts, comments, attachments, visibility, search content, hashes, verification, and optional Celo anchoring. Public visibility requires an appropriate verified or published farm registry record.
- A durable event bus provides outbox-style delivery, leases, retries, idempotency, dead letters, replay, disposal, and cross-domain insight transfer.
- A database-backed scheduler provides task dependencies, resource locks, run history, leases, retry backoff, and overlap control.
- Federation shares approved aggregate data between nodes with consent levels, query records, heartbeats, and incremental sync logs. Federation is not multi-master PostgreSQL and does not authorize arbitrary remote SQL.

The linked-data and stream interfaces are projections over governed records. Hashes, CIDs, UIDs, and transaction references may be public; private source evidence remains subject to consent and access policy.

The gateway is an optional FastAPI process with explicit route policy, API-key or capability-token authentication, rate limiting, audit logging, and fail-closed unknown-route behavior. The sandbox provides isolated analysis environments and monitoring. SDKs for Python, TypeScript, and JavaScript expose supported integration paths without bypassing canonical permissions. GeoNode-oriented services provide shapefile, KML, raster metadata, CSW, ISO 19115, thesaurus, and map-viewer interoperability. These are integration and operating surfaces, not alternate sources of truth.

## 13F. Resilience, Capital, and Simulation

Strategic reserves track carbon buffers, commons reserves, financial ring-fences, capability standby, and seed vault capacity. Health checks report held-versus-target adequacy, drawdown headroom, trigger and breach state, and a fundability signal. Preemptive deployment and release proposals are drafts requiring independent human approval; no autonomous drawdown or on-chain release is performed.

Capital accounting extends the eight Forms of Capital with capacity assessments, consumption-versus-reinvestment observations, capture-risk diagnostics, and a deferred regenerative-credit ledger. A regenerative credit is a claim on future regenerative output, not a coercive levy or automatic token reward. Agents may propose draft ledger entries only; settlement and redemption require a separate human-approved flow.

Forecast services calculate scenario outputs for revenue, NOI, yield, cost, carbon sequestration, biodiversity value, and retained value. The prediction ledger records forecasts and outcomes so accuracy can be evaluated by horizon, including Brier-style calibration where applicable. Reference-class forecasting and outside-view evidence are supported.

Simulation services are read-only and advisory. Monte Carlo wrappers perturb sampled inputs around deterministic simulators; clash examples model shocks, pests, market pressure, or reserve adequacy. They never model stakeholder fragmentation or community manipulation and never write governed state.

## 13G. Stakeholder, Governance, and Cooperative Operations

The stakeholder layer now covers the full participation lifecycle: party and relationship records, identity resolution, interests and salience, consent and portability, engagement plans and touchpoints, grievances and remedies, representation and accessibility, minority views, decisions and trade-offs, evidence and outcomes, trust profiles, and stakeholder cockpit views. Public outputs remain consented, summarized, and governed.

Governance is framework-aware. `services/governance/` exposes a read-first `GovernanceFramework` abstraction and a Moloch v3/Baal adapter for proposals, votes, members, shares, loot, configuration, and shaman permissions. The legacy Moloch v2 indexer remains separate for historical records. Governance circles, roles, authority, tensions, proposals, and tactical coordination are modeled off-chain with human approval boundaries.

Cooperative services support cooperative creation, member roles and shares, shared assets and bookings, collective purchasing, market orders, and member dashboards. These records describe coordination and governance evidence; they do not imply legal incorporation, ownership transfer, or autonomous treasury execution.

## 14. Reporting Principles and Public Interest

Kokonut Green Paper reports should be useful to partners without overstating evidence quality or exposing private stakeholder evidence.^[21]^

### Public-Interest Defaults

- Public reports use governed records and public-safe summaries, not raw private evidence.
- Stakeholder feedback is private by default. Public reports may include it only when consent is explicit and scoped for public use.
- Cultural context and well-being reports use consented summaries, governed metric observations, and aggregate language coverage only.
- Positive claims should be paired with limitations, evidence gaps, and uncertainty notes.
- Public carbon claims require Evidence Maturity Level 6, external verifier text, methodology reference, and published status.
- CIDS export is a compatibility layer; PostgreSQL and Directus remain the canonical record of governance, consent, and evidence maturity.

### Report Snapshot Fields

`services/export/report_generator.py` attaches a `public_interest` section to generated report data and writes the following `report_snapshot` fields when available:

- `public_interest_summary`
- `uncertainty_notes`
- `negative_findings`
- `affected_community_voice`

The report registry includes farm, crop, environmental, financial, EBF, stakeholder, business, strategy, process-health, ecosystem, tactical, simulation, strategic-reserve, and capital-accounting reports. `--auto` runs every registered generator for the selected scope; it does not imply that every report has sufficient source evidence.

Representative report families include:

- Ecosystem: `state_of_kokonut`, `state_of_kokonut_graphs`, `comprehensive_status`, and `dao_proposal_history`.
- Operations and resilience: `process_health`, `value_stream_map`, `strategic_reserve`, `simulation_wargame`, and `capital_accounting`.
- Strategy and business architecture: `business_plan`, `business_model_canvas`, `pitch_deck`, `capability_dashboard`, `capability_assessment`, `strategy_execution`, and `technology_roadmap`.
- Stakeholder governance: `stakeholder_landscape`, `stakeholder_engagement`, `stakeholder_grievance`, `stakeholder_representation`, `stakeholder_decision_lineage`, `stakeholder_ecosystem`, `stakeholder_outcomes`, `stakeholder_trust`, `stakeholder_value_streams`, and `stakeholder_cockpit`.
- Tactical diagnostics: `fork_opportunities`, `pin_dependency`, `promotion_ladder`, and `tactical_layer`.

### Financial Resilience And Scaling

Regenerator review feedback identified that Kokonut's long-term financial self-sustainability, risk mitigation implementation, scaling roadmap, and Green Paper finalization should be explicit rather than implied. The Green Paper treats these as governed evidence objects.^[34]^

| Record | Purpose |
|---|---|
| `financial_sustainability_plan` | Farm model, revenue streams, grant dependency, reinvestment, public-goods allocation, runway, projected revenue, and projected NOI |
| `risk_mitigation_register` | Material risks with mitigation strategy, insurance scope, oversight, technical support, owner, cadence, and residual risk |
| `scaling_roadmap_milestone` | Target region, farm model, planned farm count, capital needed, dependencies, partner requirements, and risk gates |
| `green_paper_publication_review` | Review status, open questions, approvals, target publication date, publication hash, and CID metadata |

Financial sustainability reports are planning evidence, not guarantees. Scaling milestones are readiness checkpoints, not commitments to launch farms unless capital, partner, operational, risk, and governance gates are satisfied.

### Dashboard Review

Use the Evidence Gap and Stakeholder Feedback dashboards before publishing Green Paper materials. Claims with missing evidence links, public claims below maturity thresholds, or carbon claims below Level 6 should be treated as review items rather than public proof.^[22]^

```bash
# Generate all report types for a location
python3 -m services.export.report_generator --auto --location-id UUID

# Generate climate impact report
python3 -m services.export.report_generator --type climate_impact --location-id UUID
```

### Public Report Disclaimer

Kokonut public reports are evidence summaries, not guarantees of future performance or automatic credit issuance.^[23]^

**Standard Disclaimer:** Reports may include verified records, public stakeholder summaries, modeled outputs, forecasts, and externally reviewed claims. Each claim should be interpreted with its evidence maturity level, methodology notes, reviewer context, and stated limitations.

**Carbon Disclaimer:** Carbon-balance evidence is distinct from carbon credit issuance. Public carbon claims require Evidence Maturity Level 6, external verifier text, methodology reference, and published status. EAS attestations provide verification metadata but do not replace external verification.

**Stakeholder Privacy Disclaimer:** Private stakeholder feedback remains private unless explicit consent permits publication. Public reports may include consented summaries and aggregate private/no-consent counts, but must not expose raw private feedback.

---

## 15. Common Foundations Checklist

Use this checklist before publishing impact claims, report snapshots, or Green Paper evidence.^[24]^

### 1. Useful Questions

- What decision will this evidence support?
- Who benefits from answering the question?
- Does the claim avoid implying more certainty than the evidence supports?

### 2. Stakeholder Involvement

- Which stakeholder groups are affected?
- Are stakeholder outcomes recorded separately where experience differs?
- Is stakeholder feedback consented before public use?

### 3. Feasible Data

- Are source records available in PostgreSQL/Directus?
- Are source lineage fields populated?
- Is evidence maturity appropriate for the intended use?

### 4. Sense-Making

- Has a human reviewer interpreted the result in context?
- Are limitations and negative findings documented?
- Are private/no-consent signals aggregated rather than exposed?

### 5. Reporting

- Does the public report include evidence maturity labels?
- Are carbon claims clearly separated from carbon credit issuance?
- Are public-interest fields populated on `report_snapshot`?

### 6. Learning

- Did review produce a proposed metric, workflow change, or operational action?
- Are rejected or needs-info findings retained for rework?
- Is the next reporting cycle able to improve data quality?

---

## 16. Publication Boundaries

This section defines what the Green Paper claims and what it does not claim.

### What the Green Paper Includes

| Category | Includes |
|---|---|
| **Data & Governance** | Evidence maturity levels (0-6) across claims, feedback, MRV, and reporting. Private-by-default stakeholder feedback and public-safe summaries. Public impact claims with maturity gates. Report snapshots with public-interest context. Evidence gap and stakeholder feedback dashboards. |
| **Verification & Interoperability** | CIDS v3.2.0 Essential Tier JSON-LD export. EAS on Celo for onchain/offchain attestation metadata. EBF pillar scoring with 7 dimensions, 70 rubric bands, public scorecards, trust graph provenance, calibration workflow, and portfolio messy roll-up.^[29]^ |
| **Ecological & Carbon** | Carbon and environmental impact tracking with sequestration, emissions, biodiversity, and regenerative scoring. Level 6 external verification for public carbon claims. |
| **Impact Domains** | Holistic well-being evidence with cultural context, local-language reporting, and feedback-to-action traceability.^[33]^ Financial sustainability, risk mitigation, scaling roadmap, and publication review evidence.^[34]^ Capital efficiency and utility evidence with scenario-based leverage, governance throughput, and capital-provider utility signals.^[35]^ Commons liberation and stewardship evidence with time liberation, capital alignment, governance inclusion, and land stewardship commitments.^[36]^ GNH alignment and inclusion evidence with domain-level well-being, cultural preservation, renewable energy planning, and vulnerable-group access.^[37]^ Regenerative outcomes and stewardship evidence with outcome summaries, community governance, replication readiness, and adaptive stewardship loops.^[38]^ Open Source Capitalist scaling evidence with unit economics, scaling targets, adoption barriers, stress tests, and open-source artifacts.^[39]^ Kokonut Commons governance evidence with anti-capture policies, flexible redistribution, federation protocols, algorithmic redistribution, and participatory signals.^[40]^ Bio Factory operations evidence with production batches, ingredient provenance, recipe library, quality testing, ingredient composition reference, and LAC regional input availability.^[41]^ |
| **AI & Workflows** | Agent-assisted CIDS export and feedback synthesis with draft-only outputs. |
| **Web3** | Web3 verification metadata on Celo via EAS. |

### What the Green Paper Does Not Claim

| Category | Does not claim |
|---|---|
| **Data & Verification** | CIDS export is compatibility mapping, not the canonical database.^[25]^ EAS attestations are verification metadata, not automatic proof of external verification. Carbon-balance evidence is distinct from carbon credit issuance. Private stakeholder evidence remains private unless explicit consent allows publication. |
| **Agent & AI** | Agent outputs are draft aids and must be human-reviewed. Agent capabilities described in this document are current; future capabilities are not commitments. |
| **EBF & Scoring** | EBF scores are governed assessments, not automatic certifications; calibration and rubric decisions require human review. Holistic well-being signals are learning and accountability evidence, not a guarantee of community satisfaction or cultural representation. CRISP, EBF, trend, geostatistical, systems-thinking, and simulation outputs are analytical or planning evidence unless separately governed and reviewed. |
| **Financial & Scaling** | Financial sustainability plans and scaling milestones are planning evidence, not guarantees of revenue, funding, expansion, or risk elimination. Capital efficiency reports are planning evidence, not guarantees of returns or capital deployment outcomes. Scaling targets are explicit planned numbers, not unlimited-scaling claims. |
| **Impact Domains** | Land stewardship records are commitment evidence, not legal land-transfer or landlord-abolition claims. GNH alignment is evidence of well-being signals, not Bhutan-readiness certification. Renewable energy records distinguish planned from implemented status; planned records are not operational claims. Regenerative outcome summaries are grant-reporting evidence, not performance guarantees. Replication readiness is a checkpoint signal, not a commitment to launch new farms. Participatory signal experiments are advisory only unless explicitly marked as decision-binding with human review. Redistribution policies are flexible per scenario; no single allocation percentage is hardcoded across all contexts. |
| **Bio Factory** | Batch yields, input provenance records, and quality test results are smallholder pilot evidence, not commercial production guarantees. Recipes are public knowledge for adaptation, not commercial endorsements. Quality test results are advisory, not certification. |
| **Credits & Forecasting** | The platform's governed credit issuance and retirement records are internal ledger events, not claims of external registry issuance, certification, or recognition. The platform does not provide external verification services. Forecast and modeled outputs are projections, not guarantees. |
| **Federation & Coordination** | Federation is approved aggregate-data exchange, not multi-master PostgreSQL, arbitrary remote SQL, or a cross-replica transaction layer. Threatcasting, Delphi, tactical, reserve, and simulation outputs do not authorize autonomous intervention, fund release, stakeholder manipulation, or on-chain execution. |

### Suggested Narrative

Kokonut combines PostgreSQL/Directus governance, ClickHouse analytics, Celo EAS attestations, CIDS-compatible export, stakeholder consent, agent-safe workflows, EBF pillar scoring, and seven additional evidence modules (capital efficiency, commons liberation, GNH alignment, regenerative outcomes, open-source scaling, commons governance, and bio-factory operations). The system is designed to make regenerative farm evidence comparable while preserving privacy and surfacing uncertainty.

---

## 17. Pilot Data: Kokonut Adelphi

Kokonut Adelphi (`kokonut-adelphi`) is the canonical pilot/demo farm and the first live Kokonut syntropic farm proof. It is located in Sabana Grande de Boya, Monte Plata, Dominican Republic.^[26]^

### Key Facts

| Field | Value |
|-------|-------|
| Total area | 15,725 m² |
| Agricultural land | 13,838 m² |
| Registry slug | `kokonut-adelphi` |
| Hub reference | `https://hub.kokonut.network/projects/41` |
| Public goods allocation | 10% |

### Products

- Lettuce
- Passion fruit
- Coconut
- Eggs
- Indian yam
- Nursery outputs
- Bioinputs

### Framework Alignment

Adelphi is aligned to:

- **SDGs** via `farm_impact_mapping`
- **8 Forms of Capital** (natural, social, human, financial, manufactured, intellectual, cultural, spiritual)
- **Pillars of Value** (ecological, social, economic, governance)
- **EBF dimensions** (Ecological Benefits Framework)
- **CRISP risk dimensions** (carbon yield, climate catastrophe, policy & legal, financial viability, implementation) — five-factor internal risk intelligence engine with configurable per-location weights and composite AAA-D rating
- **5 Principles of Regeneration** (care for soil, increase biodiversity, minimize external inputs, close loops, empower community)

Framework reference data is seeded by `schemas/seeds/023_impact_frameworks.sql` and Adelphi-specific mappings by `schemas/seeds/024_adelphi_alignment.sql`.^[27]^

### Seed Scripts

```bash
# Apply schema and base seeds
./scripts/seed.sh

# Apply pilot data (Kokonut Adelphi)
./scripts/seed-pilot.sh

# Compute draft governed metrics; human verification is separate
./scripts/compute-metrics.sh

# Verify MVP definition of done
./scripts/verify-platform.sh
```

### Verification

The MVP verifier asserts that Kokonut Adelphi identity, operational records, source lineage, governed metric values, public views, MRV/attestation readiness, Celo EAS schema metadata, Gnosis DAO metadata, framework reference data, Colony-backed Guild records, forecasts, dashboard datasets, environmental baselines, Web3 usage, schema versions, metric versions, and agent summary permissions are present and coherent.^[28]^

---

## 18. Glossary and References

### Glossary

| Term | Definition |
|------|------------|
| Celo | Layer-1 blockchain optimized for mobile payments and regenerative finance; primary EAS attestation chain |
| CIDS | Common Impact Data Standard — an interoperability standard for impact data |
| ClickHouse | Column-oriented analytical database for high-volume time-series and event queries |
| CO2e | Carbon dioxide equivalent — standardized greenhouse gas measurement |
| Colony | Decentralized organization protocol for task coordination and reputation tracking |
| CRISP | Carbon Risk Identification and Scoring Principles — internal farm risk intelligence engine adapted from Solid World's SW-CRISP framework |
| DAO | Decentralized Autonomous Organization — governance system operating via on-chain rules |
| Directus | Open-source headless CMS and API platform |
| EAS | Ethereum Attestation Service — onchain/offchain attestation protocol |
| EBF | Ecological Benefits Framework — 7-pillar regenerative agriculture impact assessment |
| Foundry | Solidity development toolkit for compiling, testing, and deploying smart contracts |
| Gnosis Chain | Ethereum sidechain hosting the Kokonut Moloch DAO treasury |
| IPCC | Intergovernmental Panel on Climate Change — source of emission factor references |
| IPFS | InterPlanetary File System — decentralized content storage |
| JSON-LD | JSON for Linked Data — machine-readable format for semantic web and CIDS export |
| MCP | Model Context Protocol — standardized AI agent interface |
| Moloch DAO | Gnosis-based treasury governance system used by Kokonut |
| MRV | Measurement, Reporting, and Verification |
| PostGIS | PostgreSQL spatial database extension |
| PostgreSQL | Open-source relational database — canonical data store for Kokonut |
| SDG | Sustainable Development Goal — United Nations 2030 agenda targets |
| Shannon Diversity Index | Ecological measure of species diversity |
| Solidity | Programming language for Ethereum-compatible smart contracts |
| OODA | Observe, Orient, Decide, Act; the platform's governed intelligence loop |
| CRISP | Internal five-dimension risk scoring engine with configurable weights and AAA-D bands |
| Delphi | Real-time, pseudonymous expert consultation and consensus process |
| IRI | Stable, versioned `kokonut:` identifier for a governed entity |
| RDF | Resource Description Framework used for linked-data triples |
| SPARQL | Query language translated to supported SQL patterns over RDF triples |
| BPM | Business Process Management; lifecycle, mining, prediction, control, and escalation tooling |
| EBF | Ecological Benefits Framework; seven-pillar scoring and evidence model |
| StratML | ISO 17469-1 strategy interchange projection |
| dMRV | Digital Measurement, Reporting, and Verification using sensors, remote sensing, and evidence controls |

### References

^[1]^ `docs/architecture.md` — Security model and agent scope boundaries.

^[2]^ `schemas/postgres/015_constraints.sql` — Lifecycle enum types and CHECK constraints.

^[3]^ `extensions/kokonut-hooks/src/workflow.ts:267-287` — 7-day feedback review enforcement.

^[4]^ `extensions/kokonut-hooks/src/metric-proposal.ts:27-38` — 30-day metric discussion enforcement.

^[5]^ `extensions/kokonut-hooks/src/feedback.ts`, `metric-proposal.ts`, `impact-claim.ts`, `agent-safety.ts` — Directus workflow hooks.

^[6]^ `schemas/postgres/029_impact_accountability_foundation.sql` — Evidence maturity level enforcement.

^[7]^ `services/agents/safety.py` — Agent safety preflight helpers.

^[8]^ `services/registry/cids_export.py` — CIDS v3.2.0 Essential Tier exporter.

^[9]^ `schemas/postgres/030_stakeholder_feedback.sql` — Stakeholder feedback with consent management.

^[10]^ `extensions/kokonut-hooks/src/workflow.ts:267-287` — 7-day review period enforcement.

^[11]^ `services/agents/feedback_agent.py` — Stakeholder feedback synthesis agent.

^[12]^ `schemas/postgres/031_impact_claims_and_cids.sql` — Impact claims and metric proposals.

^[13]^ `extensions/kokonut-hooks/src/impact-claim.ts` — Public claim validation and Level 6 enforcement.

^[14]^ `docs/participatory-metrics.md` — Participatory metric proposal workflow.

^[15]^ `extensions/kokonut-hooks/src/metric-proposal.ts:27-38` — 30-day discussion period enforcement.

^[16]^ `docs/agent-safety.md` — Agent safety rules and enforcement.

^[17]^ `docs/architecture.md` — EAS on Celo and deployed contracts.

^[18]^ `schemas/seeds/014_pilot_celo_eas.sql` — Celo EAS schema metadata.

^[19]^ `schemas/postgres/028_carbon_framework.sql` — Carbon framework tables.

^[20]^ `docs/public-report-disclaimer.md` — Carbon disclaimer.

^[21]^ `docs/reporting-principles.md` — Public-interest reporting principles.

^[22]^ `dashboards/metabase/20_evidence_gap_dashboard.json` — Evidence gap review dashboard.

^[23]^ `docs/public-report-disclaimer.md` — Standard, carbon, and privacy disclaimers.

^[24]^ `docs/common-foundations-checklist.md` — Claim quality checklist.

^[25]^ `docs/cids-mapping.md` — CIDS governance boundary.

^[26]^ `schemas/seeds/024_adelphi_alignment.sql` — Adelphi framework alignment.

^[27]^ `schemas/seeds/023_impact_frameworks.sql` — Framework reference data.

^[28]^ `tests/test_mvp_done.py` — MVP definition of done verifier.

^[29]^ `schemas/postgres/032_ebf_scorecard.sql` — EBF pillars, rubric bands, scorecards, scores, evidence links, and public views; `services/scoring/` — EBF scoring module.

^[30]^ `services/analytics/portfolio.py` — EBF portfolio messy roll-up; `schemas/postgres/033_ebf_p1_operations.sql` — Trust graph, calibration, and recommendation tables.

^[31]^ `services/scoring/trust_graph.py` — EBF trust graph export (JSON and Mermaid); `docs/ebf-trust-graph.md` — Trust graph model and usage guide.

^[32]^ `docs/ebf-scorecard.md` — EBF scorecard operator/reviewer guide; `services/agents/ebf_calibration_agent.py` — Calibration memo agent.

^[33]^ `schemas/postgres/034_holistic_wellbeing.sql` — Cultural context, well-being observations, participatory action records, and public-safe views; `docs/holistic-wellbeing.md` — Holistic well-being operating guide.

^[34]^ `schemas/postgres/035_financial_resilience_and_scaling.sql` — Financial sustainability plans, risk mitigation register, scaling roadmap milestones, Green Paper publication review, and public-safe views; `docs/financial-sustainability.md`, `docs/risk-mitigation.md`, and `docs/scaling-roadmap.md` — Operating guides.

^[35]^ `schemas/postgres/036_capital_efficiency_and_utility.sql` — Capital efficiency scenarios, regenerative efficiency observations, governance throughput observations, capital-provider utility scenarios, and public-safe views; `docs/capital-efficiency.md` — Scenario-evidence operating guide.

^[36]^ `schemas/postgres/037_commons_liberation_and_stewardship.sql` — Time liberation observations, capital alignment assessments, governance inclusion observations, land stewardship commitments, and public-safe views; `docs/commons-liberation.md` — Commons evidence operating guide.

^[37]^ `schemas/postgres/038_gnh_alignment_and_inclusion.sql` — GNH alignment assessments, cultural preservation plans, renewable energy plans, vulnerable group access plans, foundational well-being observations, and public-safe views; `docs/gnh-alignment.md` — GNH evidence operating guide.

^[38]^ `schemas/postgres/039_regenerative_outcomes_and_stewardship.sql` — Regenerative outcome summaries, community governance mechanisms, replication readiness assessments, adaptive stewardship reviews, and public-safe views; `docs/regenerative-outcomes.md` — Regenerator review operating guide.

^[39]^ `schemas/postgres/040_open_source_capitalist_scaling.sql` — Farm launch unit economics, network scaling targets, adoption barrier assessments, perpetual value stress tests, open-source impact artifacts, and public-safe views; `docs/open-source-capitalist-scaling.md` — scaling economics operating guide.

^[40]^ `schemas/postgres/041_kokonut_commons_governance.sql` — Anti-capture governance policies, flexible redistribution policies, federation protocols, algorithmic redistribution mechanisms, participatory signal experiments, and public-safe views; `docs/kokonut-commons-governance.md` — Kokonut Commons governance operating guide.

^[41]^ `schemas/postgres/043_bio_factory_operations.sql` — Bio-factory batches, provenance, recipes, quality tests, composition references, and regional input availability; `docs/bio-factory-operations.md` — operating guide.

^[42]^ `services/orientation/`, `services/decision/`, `services/feedback/`, and `schemas/postgres/124_orientation.sql` through `127_ooda_cycles.sql` — OODA assessment, policy, feedback, and cycle tracking.

^[43]^ `services/crisp/` and `schemas/postgres/076_crisp_risk_scoring.sql` — configurable CRISP risk scoring.

^[44]^ `services/threatcasting/`, `services/delphi/`, `schemas/postgres/159_threatcasting.sql`, and `161_delphi.sql` — threatcasting, backcasting, probability forecasting, Delphi consultation, and human-approved recommendations.

^[45]^ `services/workflow_specs/`, `services/analytics/process_mining.py`, `services/analytics/predictive_bpm.py`, and `schemas/postgres/182_process_mining.sql` through `195_service_catalog.sql` — workflow specifications and BPM tooling.

^[46]^ `services/iri/`, `services/rdf/`, `services/linkml/`, `services/graph_projection/`, and `services/data_stream/` — linked data, identity, evidence lineage, and governed data streams.

^[47]^ `services/strategic_reserve/`, `services/capital/`, `services/simulation/`, and migrations `327` through `330` — resilience reserves, capital accounting, and advisory simulation.

^[48]^ `services/export/report_generator.py` — registered report generators and report snapshot public-interest fields.

---

## Appendix A: Review Commands

```bash
# Schema and seeds
./scripts/seed.sh
./scripts/seed-pilot.sh
./scripts/compute-metrics.sh
./scripts/verify-platform.sh

# CIDS export
python3 -m services.registry.cids_export --location-id UUID

# AI summary (requires verified/published farm_registry_record)
python3 -m services.agents.ai_summary --location-id UUID --summary-type combined
python3 -m services.agents.ai_summary --location-id UUID --summary-type combined --store

# CIDS export agent (read-only)
python3 -m services.agents.cids_agent --location-id UUID --summary

# Feedback synthesis
python3 -m services.agents.feedback_agent --location-id UUID
python3 -m services.agents.feedback_agent --location-id UUID --store

# Holistic well-being synthesis
python3 -m services.agents.wellbeing_agent --location-id UUID
python3 -m services.agents.wellbeing_agent --location-id UUID --store

# Financial resilience and scaling synthesis
python3 -m services.agents.resilience_agent --location-id UUID
python3 -m services.agents.resilience_agent --location-id UUID --store

# Capital efficiency and utility synthesis
python3 -m services.agents.capital_efficiency_agent --location-id UUID
python3 -m services.agents.capital_efficiency_agent --location-id UUID --store

# Commons liberation and stewardship synthesis
python3 -m services.agents.commons_agent --location-id UUID
python3 -m services.agents.commons_agent --location-id UUID --store

# GNH alignment synthesis
python3 -m services.agents.gnh_agent --location-id UUID
python3 -m services.agents.gnh_agent --location-id UUID --store

# Regenerative outcomes synthesis
python3 -m services.agents.regenerator_agent --location-id UUID
python3 -m services.agents.regenerator_agent --location-id UUID --store

# Open Source Capitalist scaling synthesis
python3 -m services.agents.open_source_capitalist_agent --location-id UUID
python3 -m services.agents.open_source_capitalist_agent --location-id UUID --store

# Kokonut Commons governance synthesis
python3 -m services.agents.kokonut_commons_agent --location-id UUID
python3 -m services.agents.kokonut_commons_agent --location-id UUID --store

# EBF scoring
python3 -m services.scoring --location-id UUID

# EBF portfolio
python3 -m services.analytics --ebf-portfolio-summary

# EBF agents
python3 -m services.agents.ebf_scorecard_agent --location-id UUID --draft
python3 -m services.agents.ebf_evidence_gap_agent --location-id UUID
python3 -m services.agents.ebf_calibration_agent --location-id UUID --draft

# Report generation (--auto generates every registered report type)
python3 -m services.export.report_generator --auto --location-id UUID

# Core reports
python3 -m services.export.report_generator --type farm_summary --location-id UUID
python3 -m services.export.report_generator --type crop_noi --location-id UUID
python3 -m services.export.report_generator --type environmental --location-id UUID
python3 -m services.export.report_generator --type revenue_multiplier --location-id UUID
python3 -m services.export.report_generator --type forecast --location-id UUID
python3 -m services.export.report_generator --type climate_impact --location-id UUID
python3 -m services.export.report_generator --type ebf_scorecard --location-id UUID

# Impact and well-being reports
python3 -m services.export.report_generator --type holistic_wellbeing --location-id UUID
python3 -m services.export.report_generator --type financial_sustainability --location-id UUID
python3 -m services.export.report_generator --type risk_mitigation --location-id UUID
python3 -m services.export.report_generator --type scaling_roadmap --location-id UUID
python3 -m services.export.report_generator --type green_paper_publication_status --location-id UUID

# Capital efficiency reports
python3 -m services.export.report_generator --type capital_efficiency --location-id UUID
python3 -m services.export.report_generator --type governance_throughput --location-id UUID
python3 -m services.export.report_generator --type capital_provider_utility --location-id UUID

# Commons liberation reports
python3 -m services.export.report_generator --type time_liberation --location-id UUID
python3 -m services.export.report_generator --type capital_alignment --location-id UUID
python3 -m services.export.report_generator --type governance_inclusion --location-id UUID
python3 -m services.export.report_generator --type land_stewardship --location-id UUID

# GNH alignment reports
python3 -m services.export.report_generator --type gnh_alignment --location-id UUID
python3 -m services.export.report_generator --type cultural_preservation --location-id UUID
python3 -m services.export.report_generator --type renewable_energy --location-id UUID
python3 -m services.export.report_generator --type vulnerable_access --location-id UUID
python3 -m services.export.report_generator --type foundational_wellbeing --location-id UUID

# Regenerative outcomes reports
python3 -m services.export.report_generator --type regenerative_outcomes --location-id UUID
python3 -m services.export.report_generator --type community_governance --location-id UUID
python3 -m services.export.report_generator --type replication_readiness --location-id UUID
python3 -m services.export.report_generator --type adaptive_stewardship --location-id UUID

# Open Source Capitalist scaling reports
python3 -m services.export.report_generator --type scaling_economics --location-id UUID
python3 -m services.export.report_generator --type adoption_barriers --location-id UUID
python3 -m services.export.report_generator --type perpetual_value_stress --location-id UUID
python3 -m services.export.report_generator --type open_source_impact --location-id UUID

# Kokonut Commons governance reports
python3 -m services.export.report_generator --type anti_capture_governance --location-id UUID
python3 -m services.export.report_generator --type redistribution_policy --location-id UUID
python3 -m services.export.report_generator --type federation_mutual_aid --location-id UUID
python3 -m services.export.report_generator --type algorithmic_redistribution --location-id UUID
python3 -m services.export.report_generator --type participatory_signal --location-id UUID

# Unified CLI and platform operations
python3 -m services.cli --help
python3 -m services.workflow_specs validate
python3 -m services.graph_projection rebuild --actor OPERATOR
python3 -m services.events --stats
python3 -m services.scheduler.cli --status
python3 -m services.federation.cli --list-nodes

# OODA, CRISP, trends, and geostatistics
python3 -m services.decision.policies --pending --location-id UUID
python3 -m services.crisp --composite --location-id UUID --period-start YYYY-MM-DD --period-end YYYY-MM-DD
python3 -m services.trends.dashboard --location-id UUID --alerts
python3 -m services.geostatistics.cli spatial-cv-soc --location-id UUID --block-size 200

# Threatcasting and Delphi
python3 -m services.threatcasting briefing --location-id UUID
python3 -m services.threatcasting cascade-risk --location-id UUID
python3 -m services.delphi live-summary --study-id UUID
python3 -m services.delphi check-stopping --study-id UUID

# Identity, linked data, and data stream
python3 -m services.iri.cli generate --entity-type location --entity-id UUID
python3 -m services.rdf.cli build --location-id UUID
python3 -m services.rdf.cli query --subject "kokonut:location:UUID"
python3 -m services.data_stream.cli stream --location-id UUID

# Resilience, capital, prediction, and simulation
python3 -m services.strategic_reserve.cli health
python3 -m services.capital.cli report --location-id UUID
python3 -m services.predictions --help
python3 -m services.export.report_generator --type simulation_wargame --location-id UUID

# Strategy, planning, and process health
python3 -m services.planning budget variance --id UUID
python3 -m services.planning cockpit show --org-id UUID
python3 -m services.analytics.process_mining discover --entity-type TYPE
python3 -m services.analytics.predictive_bpm breaches --entity-type TYPE --sla-target-hours 72
```

---

*This document is the Codebase Parity Draft. Claims and commands are aligned to the current repository structure, but human stakeholder sign-off and a final execution review remain required before public release.*
