# Kokonut Intelligence Platform — Green Paper V1

**Version:** 1.0  
**Date:** June 2026  
**Status:** Draft for Publication Review  
**License:** Open Source

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [System Architecture](#3-system-architecture)
4. [Data Lifecycle](#4-data-lifecycle)
5. [Evidence Maturity Model](#5-evidence-maturity-model)
6. [CIDS Mapping and Export](#6-cids-mapping-and-export)
7. [Stakeholder Feedback](#7-stakeholder-feedback)
8. [Impact Claims and Metric Proposals](#8-impact-claims-and-metric-proposals)
9. [Agent Safety and Workflows](#9-agent-safety-and-workflows)
10. [Web3 Verification](#10-web3-verification)
11. [Carbon and Environmental Impact](#11-carbon-and-environmental-impact)
12. [Reporting Principles and Public Interest](#12-reporting-principles-and-public-interest)
13. [Common Foundations Checklist](#13-common-foundations-checklist)
14. [Publication Boundaries](#14-publication-boundaries)
15. [Pilot Data: Kokonut Adelphi](#15-pilot-data-kokonut-adelphi)
16. [Glossary and References](#16-glossary-and-references)

---

## 1. Executive Summary

Kokonut Intelligence is an open-source intelligence layer for regenerative farm operations, financial performance, ecological outcomes, partner reporting, and Web3 verification. It is designed to make regenerative farm evidence comparable while preserving privacy and surfacing uncertainty.

The platform combines PostgreSQL and Directus as the canonical schema and API layer, ClickHouse for analytical events, Python services for metrics and forecasting, EAS on Celo for public verification metadata, and Gnosis Moloch DAO for treasury governance. The system is built to serve farm operators, partners, reviewers, and the broader regenerative agriculture community.

### Core Principles

1. **The schema is the product.** Dashboards, spreadsheets, agents, and blockchain views are interfaces. The durable asset is the canonical schema, metric dictionary, verification logic, and API contract.

2. **Web3 is a proof layer, not source of truth.** Canonical operational and financial data lives in PostgreSQL. Blockchain provides proofs, coordination, and public verifiability.

3. **Humans and AI agents use the same governed objects.** Different interfaces over the same canonical objects, permissions, and audit trails.

4. **Private evidence stays off-chain by default.** Public surfaces store hashes, CIDs, attestation UIDs, chain labels, and transaction hashes. Raw private MRV payloads remain in controlled off-chain storage.

### Key Capabilities

- Governed farm operations across 40+ collections with role-based access.
- Multi-source ingestion from weather, market prices, remote sensing, sensors, EAS attestations, and Gnosis DAO activity.
- 17 governed metric definitions with calculator-backed results, public aggregate views, and dashboard datasets.
- Evidence maturity model (levels 0-6) enforced across claims, feedback, MRV, and reporting.
- CIDS v3.2.0 Essential Tier JSON-LD export for impact data interoperability.
- Private-by-default stakeholder feedback with consent management and public-safe summaries.
- EAS on Celo for onchain/offchain attestations with attester-gating via KokonutResolver.
- Carbon and environmental impact tracking with sequestration, emissions, biodiversity, and regenerative scoring.
- Agent-assisted CIDS export, feedback synthesis, and report preparation with draft-only outputs.
- Report snapshots with public-interest context, limitations, uncertainty notes, and negative findings.
- EBF pillar scoring across 7 dimensions with 70 rubric bands, public scorecards, trust graph provenance, and calibration workflow.^[29]^
- Portfolio messy roll-up comparison by pillar, confidence, and maturity with explicit caveats, not farm ranking.^[30]^
- Holistic well-being evidence for cultural context, local-language reporting, community trust, operator capability, and participatory feedback-to-action traceability.^[33]^
- Financial resilience evidence for grant dependency, reinvestment, public-goods allocation, runway, risk mitigation, scaling milestones, and Green Paper publication status.^[34]^
- Capital efficiency and utility evidence for scenario-based capital leverage, regenerative practice payback, DAO/community governance throughput, and capital-provider utility limitations.^[35]^
- Commons liberation and stewardship evidence for time reclaimed, capital alignment, governance inclusion, pseudonymous participation boundaries, and land stewardship commitments.^[36]^
- GNH alignment evidence for domain-level well-being, cultural preservation, renewable energy planning, vulnerable-group access, and foundational well-being signals.^[37]^
- Regenerative outcomes and stewardship evidence for concise impact summaries, community decision mechanisms, replication readiness, and adaptive management loops.^[38]^

---

## 2. Problem Statement

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

## 3. System Architecture

### Technology Stack

| Layer | Technology | Role |
|-------|------------|------|
| Canonical core | PostgreSQL 14 + PostGIS 3.4 + Directus 11.17 | Schema, API, permissions, workflows, data entry UI |
| Analytics | ClickHouse 25.3 | Time-series events and high-volume analytical queries |
| BI | Metabase | Internal dashboards and aggregate reporting |
| Intelligence | Python services | Metrics, forecasts, scoring, exports, ingestion, AI summaries |
| Verification | EAS on Celo + offchain evidence storage | Onchain attestations, offchain signed claims, MRV proof metadata |
| Governance and Guilds | Gnosis Moloch DAO + Colony metadata | Treasury governance, Guild contribution records, reputation snapshots |
| Contracts | Foundry + Solidity | KokonutResolver attester gating for EAS schemas |

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
│  weather.py       → OpenWeatherMap API                  │
│  rpc_indexer.py   → Ethereum/L2 public RPC              │
│  market_data.py   → World Bank Pink Sheet               │
│  remote_sensing.py → CSV upload (NDVI/NDRE)            │
│  eas_indexer.py   → EAS GraphQL API (Celo/Optimism/Base)   │
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

### Security Model

- **Roles:** Administrator, Field Worker, Supervisor, Manager, Finance, Analyst.
- **Policies:** Per-collection, per-action, per-field permissions (84 rules across 5 policies).
- **Field-level:** Sensitive fields hidden per role.
- **Row-level:** Filter rules restrict record visibility.
- **Audit:** All mutations logged to `audit_log`.
- **Evidence:** Raw evidence stored off-chain; hashes/CIDs on-chain.
- **Agent scope:** This repository stores agent metadata and tasks only; marketplace identity, payment, escrow, and reputation logic are external.^[1]^

### Schema Management

Schemas are version-controlled as SQL files in `schemas/postgres/`. Directus snapshots capture the API-layer state. ClickHouse schemas live in `schemas/clickhouse/`. Seed data lives in `schemas/seeds/`.

---

## 4. Data Lifecycle

Every important record follows a canonical four-state lifecycle:

```
draft → submitted → verified → published
```

- **Draft:** Record created; source payload preserved where available.
- **Submitted:** Mapped to Kokonut canonical schema and submitted for review.
- **Verified:** Reviewed, validated, linked to evidence.
- **Published:** Available to dashboards, APIs, attestations.

`rejected` is available for rework and exception paths. Payment, attestation, execution, and domain-specific states live in dedicated fields such as `payment_status`, `attestation_uid`, `attested_at`, `execution_status`, and `revocation_date`.^[2]^

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

Directus hooks enforce review workflows for stakeholder feedback, stakeholder outcomes, impact claims, metric proposals, agent tasks, AI summaries, and agent action logs.^[5]^

---

## 5. Evidence Maturity Model

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

## 6. CIDS Mapping and Export

Kokonut targets Common Impact Data Standard (CIDS) v3.2.0 Essential Tier for Green Paper V1. PostgreSQL/Directus remains the canonical data layer; CIDS is an export compatibility layer.^[8]^

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

## 7. Stakeholder Feedback

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

Grant-review feedback highlighted that Kokonut's cultural heritage, local-language accessibility, participatory governance, and holistic well-being evidence should be explicit rather than implied. Green Paper V1 now treats these as governed public-safe evidence objects.^[33]^

| Record | Purpose |
|---|---|
| `cultural_context_record` | Local-language needs, traditional knowledge boundaries, heritage species, community stories, and land-memory context |
| `wellbeing_metric_observation` | Operator capability, community trust, worker safety, training access, benefit transparency, and cultural-capital observations |
| `participatory_action_record` | Traceability from stakeholder feedback to metric proposals, report changes, governance review, or operator actions |

Public cultural context requires explicit consent, public scope, published status, and a non-empty public summary. Raw cultural knowledge, household-level observations, and non-consented feedback remain private.

---

## 8. Impact Claims and Metric Proposals

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

## 9. Agent Safety and Workflows

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

## 10. Web3 Verification

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

## 11. Carbon and Environmental Impact

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

Carbon-balance evidence is distinct from carbon credit issuance. Public carbon claims require Evidence Maturity Level 6, external verifier text, methodology reference, and published status. EAS attestations provide verification metadata but do not replace external verification.^[20]^

---

## 12. Reporting Principles and Public Interest

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

### Financial Resilience And Scaling

Regenerator review feedback identified that Kokonut's long-term financial self-sustainability, risk mitigation implementation, scaling roadmap, and Green Paper finalization should be explicit rather than implied. Green Paper V1 now treats these as governed evidence objects.^[34]^

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

## 13. Common Foundations Checklist

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

## 14. Publication Boundaries

This section defines what Green Paper V1 claims and what it does not claim.

### What Green Paper V1 Includes

- CIDS v3.2.0 Essential Tier JSON-LD export.
- Evidence maturity levels across claims, feedback, MRV, and reporting.
- Private-by-default stakeholder feedback and public-safe summaries.
- Public impact claims with maturity gates.
- Level 6 external verification for public carbon claims.
- Evidence gap and stakeholder feedback dashboards.
- Report snapshots with public-interest context.
- Holistic well-being evidence with cultural context, local-language reporting, and feedback-to-action traceability.
- Financial sustainability, risk mitigation, scaling roadmap, and Green Paper publication review evidence.
- Agent-assisted CIDS export and feedback synthesis with draft-only outputs.
- Carbon and environmental impact tracking with sequestration, emissions, biodiversity, and regenerative scoring.
- EBF pillar scoring with 7 dimensions, 70 rubric bands, public scorecards, trust graph provenance, calibration workflow, and portfolio messy roll-up.^[29]^
- Web3 verification metadata on Celo via EAS.

### What Green Paper V1 Does Not Claim

- CIDS export is compatibility mapping, not the canonical database.^[25]^
- EAS attestations are verification metadata, not automatic proof of external verification.
- Carbon-balance evidence is distinct from carbon credit issuance.
- Private stakeholder evidence remains private unless explicit consent allows publication.
- Agent outputs are draft aids and must be human-reviewed.
- EBF scores are governed assessments, not automatic certifications; calibration and rubric decisions require human review.
- Holistic well-being signals are learning and accountability evidence, not a guarantee of community satisfaction or cultural representation.
- Financial sustainability plans and scaling milestones are planning evidence, not guarantees of revenue, funding, expansion, or risk elimination.
- Forecast and modeled outputs are projections, not guarantees.
- The platform does not issue carbon credits or provide external verification services.
- Agent capabilities described in this document are current; future capabilities are not commitments.

### Suggested Narrative

Kokonut combines PostgreSQL/Directus governance, ClickHouse analytics, Celo EAS attestations, CIDS-compatible export, stakeholder consent, and agent-safe workflows. The system is designed to make regenerative farm evidence comparable while preserving privacy and surfacing uncertainty.

---

## 15. Pilot Data: Kokonut Adelphi

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
- **CRISP risk dimensions** (climate, regulatory, market, operational, reputational)
- **5 Principles of Regeneration** (care for soil, increase biodiversity, minimize external inputs, close loops, empower community)

Framework reference data is seeded by `schemas/seeds/023_impact_frameworks.sql` and Adelphi-specific mappings by `schemas/seeds/024_adelphi_alignment.sql`.^[27]^

### Seed Scripts

```bash
# Apply schema and base seeds
./scripts/seed.sh

# Apply pilot data (Kokonut Adelphi)
./scripts/seed-pilot.sh

# Compute verified governed metrics
./scripts/compute-metrics.sh

# Verify MVP definition of done
./scripts/verify-mvp.sh
```

### Verification

The MVP verifier asserts that Kokonut Adelphi identity, operational records, source lineage, governed metric values, public views, MRV/attestation readiness, Celo EAS schema metadata, Gnosis DAO metadata, framework reference data, Colony-backed Guild records, forecasts, dashboard datasets, environmental baselines, Web3 usage, schema versions, metric versions, and agent summary permissions are present and coherent.^[28]^

---

## 16. Glossary and References

### Glossary

| Term | Definition |
|------|------------|
| CIDS | Common Impact Data Standard — an interoperability standard for impact data |
| EAS | Ethereum Attestation Service — onchain/offchain attestation protocol |
| EBF | Earth Billion Futures — regenerative agriculture impact framework |
| CRISP | Climate Risk and Impact Assessment framework |
| MRV | Measurement, Reporting, and Verification |
| IPFS | InterPlanetary File System — decentralized content storage |
| CID | Content Identifier — IPFS hash for content-addressed data |
| CO2e | Carbon dioxide equivalent — standardized greenhouse gas measurement |
| Shannon Diversity Index | Ecological measure of species diversity |
| Moloch DAO | Gnosis-based treasury governance system |
| Colony | Decentralized organization for task coordination and reputation |
| MCP | Model Context Protocol — standardized AI agent interface |
| Directus | Open-source headless CMS and API platform |
| PostGIS | PostgreSQL spatial database extension |

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

---

## Green Paper Review Commands

```bash
# Schema and seeds
./scripts/seed.sh
./scripts/seed-pilot.sh
./scripts/compute-metrics.sh
./scripts/verify-mvp.sh

# CIDS export
python3 -m services.registry.cids_export --location-id UUID

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

# Report generation
python3 -m services.export.report_generator --auto --location-id UUID
python3 -m services.export.report_generator --type holistic_wellbeing --location-id UUID
python3 -m services.export.report_generator --type financial_sustainability --location-id UUID
python3 -m services.export.report_generator --type risk_mitigation --location-id UUID
python3 -m services.export.report_generator --type scaling_roadmap --location-id UUID
python3 -m services.export.report_generator --type green_paper_publication_status --location-id UUID
python3 -m services.export.report_generator --type capital_efficiency --location-id UUID
python3 -m services.export.report_generator --type governance_throughput --location-id UUID
python3 -m services.export.report_generator --type capital_provider_utility --location-id UUID
python3 -m services.export.report_generator --type time_liberation --location-id UUID
python3 -m services.export.report_generator --type capital_alignment --location-id UUID
python3 -m services.export.report_generator --type governance_inclusion --location-id UUID
python3 -m services.export.report_generator --type land_stewardship --location-id UUID
python3 -m services.export.report_generator --type gnh_alignment --location-id UUID
python3 -m services.export.report_generator --type cultural_preservation --location-id UUID
python3 -m services.export.report_generator --type renewable_energy --location-id UUID
python3 -m services.export.report_generator --type vulnerable_access --location-id UUID
python3 -m services.export.report_generator --type foundational_wellbeing --location-id UUID
python3 -m services.export.report_generator --type regenerative_outcomes --location-id UUID
python3 -m services.export.report_generator --type community_governance --location-id UUID
python3 -m services.export.report_generator --type replication_readiness --location-id UUID
python3 -m services.export.report_generator --type adaptive_stewardship --location-id UUID

# EBF scoring
python3 -m services.scoring --location-id UUID

# EBF portfolio
python3 -m services.analytics --ebf-portfolio-summary

# EBF agents
python3 -m services.agents.ebf_scorecard_agent --location-id UUID --draft
python3 -m services.agents.ebf_evidence_gap_agent --location-id UUID
python3 -m services.agents.ebf_calibration_agent --location-id UUID --draft
```

---

*This document is a draft for publication review. Human stakeholder approval is required before final publication.*
