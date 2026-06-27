# Kokonut Intelligence Platform

Open-source intelligence layer for regenerative farm operations, financial performance, ecological outcomes, partner reporting, and Web3 verification.

PostgreSQL and Directus are the canonical schema/API layer. ClickHouse stores analytical events. Python services compute metrics, forecasts, exports, registry payloads, AI summaries, and ingestion jobs. EAS on Celo anchors public verification metadata while private evidence stays offchain.

## Table Of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Local Services](#local-services)
- [MVP Verification](#mvp-verification)
- [Pilot Data And Frameworks](#pilot-data-and-frameworks)
- [Core Capabilities](#core-capabilities)
- [Data Lifecycle And Roles](#data-lifecycle-and-roles)
- [Metrics And Intelligence](#metrics-and-intelligence)
- [Web3 Verification](#web3-verification)
- [Impact Accountability And CIDS](#impact-accountability-and-cids)
- [Dashboards Reports And Export](#dashboards-reports-and-export)
- [Agents Registry And MCP](#agents-registry-and-mcp)
- [Green Paper V1](#green-paper-v1)
- [Developer Commands](#developer-commands)
- [Repository Layout](#repository-layout)
- [Security And Privacy](#security-and-privacy)
- [Documentation](#documentation)
- [License](#license)

## Architecture

| Layer | Technology | Role |
|-------|------------|------|
| Canonical core | PostgreSQL 14 + PostGIS 3.4 + Directus 11.17 | Schema, API, permissions, workflows, data entry UI |
| Analytics | ClickHouse 25.3 | Time-series events and high-volume analytical queries |
| BI | Metabase | Internal dashboards and aggregate reporting |
| Intelligence | Python services | Metrics, forecasts, scoring, exports, ingestion, AI summaries |
| Verification | EAS on Celo + offchain evidence storage | Onchain attestations, offchain signed claims, MRV proof metadata |
| Governance and Guilds | Gnosis Moloch DAO + Colony metadata | Treasury governance, Guild contribution records, reputation snapshots |
| Contracts | Foundry + Solidity | KokonutResolver attester gating for EAS schemas |

See [Architecture](docs/architecture.md) for system design, data flow, and security model details.

## Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with local secrets before starting services.

# 2. Start infrastructure
docker compose up -d

# 3. Apply schema, base seeds, and pilot data
./scripts/seed.sh
./scripts/seed-pilot.sh

# 4. Compute verified governed metrics for public views
./scripts/compute-metrics.sh

# 5. Verify the MVP definition of done
./scripts/verify-mvp.sh
```

Run the full local check with:

```bash
./scripts/ci-check.sh
```

For sandbox-specific setup, see [Developer Sandbox](docs/sandbox.md). For deployment guidance, see [Deployment](docs/deployment.md).

## Local Services

Base `docker-compose.yml` exposes Caddy on the host and keeps PostgreSQL, ClickHouse, Directus, and Metabase on Docker networks unless an overlay or local override maps additional ports.

| Service | Base URL | Notes |
|---------|----------|-------|
| Caddy | `https://localhost` | TLS termination, reverse proxy, security headers |
| Directus API | `https://localhost/directus` | Canonical API and data access |
| Directus admin | `https://localhost/admin` | Admin UI and data entry |
| Metabase | `https://localhost/metabase` | BI dashboards |
| PostgreSQL | Docker service `database:5432` | Canonical data store; use `docker compose exec database ...` |
| ClickHouse | Docker service `clickhouse:8123` | Analytical store; use Docker network or `docker compose exec clickhouse ...` |

Optional local overrides may expose Directus at `http://localhost:8055` and Metabase at `http://localhost:3001`. Use those direct URLs only if your Compose override maps the ports.

## MVP Verification

The MVP verifier checks a seeded pilot database, not just source files. It asserts that Kokonut Adelphi identity, operational records, source lineage, governed metric values, public views, MRV/attestation readiness, Celo EAS schema metadata, Gnosis DAO metadata, framework reference data, Colony-backed Guild records, forecasts, dashboard datasets, environmental baselines, Web3 usage, schema versions, metric versions, and agent summary permissions are present and coherent.

```bash
./scripts/seed.sh
./scripts/seed-pilot.sh
./scripts/compute-metrics.sh
./scripts/verify-mvp.sh
```

`./scripts/compute-metrics.sh` runs `python3 -m services.metrics --compute --all-locations --verify --json`, so public aggregate views only surface verified metric results.

## Pilot Data And Frameworks

`./scripts/seed-pilot.sh` seeds Kokonut Adelphi as the canonical pilot location. Adelphi replaces the earlier Kisumu demo and represents the first live Kokonut syntropic farm proof in Sabana Grande de Boya, Monte Plata, Dominican Republic.

Key seeded facts:

- Total area: `15,725 m2`; agricultural land: `13,838 m2`.
- Products: lettuce, passion fruit, coconut, eggs, Indian yam, nursery outputs, and bioinputs.
- Public goods allocation: `10%`.
- Registry slug: `kokonut-adelphi`.
- Hub reference: `https://hub.kokonut.network/projects/41`.

Framework reference data is seeded by `schemas/seeds/023_impact_frameworks.sql` and Adelphi-specific mappings by `schemas/seeds/024_adelphi_alignment.sql`. These cover SDGs, 8 Forms of Capital, Pillars of Value, EBF dimensions, CRISP risk dimensions, 5 regeneration principles, farm zones, syntropic practice evidence, Colony-backed Guild records, and DAO proposal metadata.

Public aggregate views require a verified or published Farm Registry record before a location appears publicly.

## Core Capabilities

- **Governed farm operations**: Activities, harvests, sales, expenses, losses, labor, field notes, inventory, maintenance, revenue events, and partner-scoped access through Directus.
- **Multi-source ingestion**: Weather, market prices, remote sensing, sensors, EAS attestations, Gnosis DAO activity, wallet events, and GIS boundaries through `services/ingestion/`.
- **Metrics and reporting**: Versioned metric definitions, calculator-backed `metric_value` records, public aggregate views, dashboard datasets, report snapshots, and CSV/JSON/Parquet exports.
- **Impact accountability**: Evidence maturity levels, stakeholder feedback, stakeholder outcomes, impact claims, participatory metric proposals, public-safe views, and CIDS Essential Tier JSON-LD export.
- **Forecasting and analytics**: Scenario forecasts, Fortune 500-style farm scoring, ecological analytics, water access, revenue multiplier opportunity maps, and AI-generated summaries.
- **Web3 verification**: EAS schemas on Celo, KokonutResolver attester gating, onchain/offchain attestations, private evidence hashes, wallet activity, and public attestation summaries.
- **Impact framework alignment**: SDGs, 8 Forms of Capital, Pillars of Value, EBF/CRISP mappings, regeneration principles, syntropic zones, and practice evidence.
- **Guild coordination**: Colony-backed Guild metadata, contribution records, reputation snapshots, and DAO proposal links while Gnosis Moloch remains the treasury governance layer.
- **Agent ecosystem**: Agent identities, capability manifests, tasks, action logs, AI summaries, and scoped MCP/Directus access. Contract identity, payments, escrow, and marketplace logic remain external to this repo.

## Data Lifecycle And Roles

Governed records use the canonical lifecycle:

```text
draft -> submitted -> verified -> published
```

`rejected` is available for rework and exception paths. Payment, attestation, execution, and domain-specific states live in dedicated fields such as `payment_status`, `attestation_uid`, `attested_at`, `execution_status`, and `revocation_date`.

| Role | Access | Description |
|------|--------|-------------|
| Administrator | Full | Platform admin and all permissions |
| Field Worker | Create/read scoped records | Data entry; records start as `draft` and create permissions exclude lifecycle audit fields |
| Supervisor | Read all, submit | Submits records for review |
| Manager | Approve/verify operational records | Reviews and verifies governed operations |
| Finance | Finance approvals | Approves expenses, verifies sales, and approves revenue events |
| Analyst | Read verified/published | Read-only analysis over governed data |

Directus hooks enforce review workflows for stakeholder feedback, stakeholder outcomes, impact claims, metric proposals, agent tasks, AI summaries, and agent action logs. Stakeholder feedback is private by default and requires explicit public consent plus a non-empty `public_summary` before public exposure. Public carbon claims require Evidence Maturity Level 6, external verifier text, and methodology reference.

Workflow time-based enforcement:
- Stakeholder feedback requires a minimum 7-day review period before verification.
- Metric proposals require a minimum 30-day discussion period before approval.

See [User Guide](docs/user-guide.md) for role workflows and data-entry walkthroughs.

## Metrics And Intelligence

The metric engine stores computed results in `metric_value` with source lineage, computation method, metadata, period, and verification state. Current registered calculator keys are:

`value_flowed`, `wallet_retention`, `digital_lego_usage`, `attestation_coverage`, `soil_carbon_delta`, `biodiversity_delta`, `operating_margin_pct`, `crop_revenue`, `net_crop_revenue`, `direct_crop_cost`, `allocated_shared_cost`, `crop_noi`, `loss_rate_pct`, `baseline_revenue`, `baseline_asset_value`, `baseline_cash_flow`, `baseline_cost`.

```bash
# List metric definitions
python3 -m services.metrics --list

# Compute one metric for one location
python3 -m services.metrics --compute --metric value_flowed --location-id UUID

# Compute all metrics for all locations and mark results verified
python3 -m services.metrics --compute --all-locations --verify
```

Additional intelligence services include:

| Service | Example |
|---------|---------|
| Fortune 500 farm scoring | `python3 -m services.fortune500.cli --all` |
| Forecast scenarios | `python3 -m services.forecast.cli --all` |
| Forecast details | `python3 -m services.forecast.cli --scenario-id UUID --details` |
| Revenue multiplier | `python3 -m services.revenue_multiplier.cli --location-id UUID` |
| Environmental analytics | `python3 -m services.analytics --environmental-baseline --location-id UUID` |
| Portfolio theme summary | `python3 -m services.analytics --portfolio-summary` |
| EBF scorecard export | `python3 -m services.scoring --scorecard-id UUID --export public` |
| EBF trust graph export | `python3 -m services.scoring --trust-graph UUID --public-safe` |
| Run EBF P0 tests | `python3 -m tests.test_ebf_p0` |
| Run EBF P1 tests | `python3 -m tests.test_ebf_p1` |
| AI summary | `python3 -m services.agents.ai_summary --location-id UUID --summary-type combined` |

See [Data Dictionary](docs/data-dictionary.md) for governed metric definitions and [User Guide](docs/user-guide.md) for analytics workflows.

## Web3 Verification

Celo is the primary EAS attestation chain. EAS v1.3.0 is deployed on Celo mainnet, and `KokonutResolver` gates attestation to allowed attesters under Kokonut multisig ownership.

Celo is the source of truth for Kokonut EAS schemas. Gnosis Chain is the source of truth for the Kokonut Moloch DAO treasury. Colony metadata in this repo records planned/observed Guild execution and reputation state; it does not replace Moloch treasury governance.

README intentionally links to the source-of-truth EAS details instead of duplicating schema UIDs and contract tables:

- [Attestation Guide](docs/attestation-guide.md)
- `services/attestation/config.py`
- `services/attestation/schemas.py`
- `schemas/seeds/014_pilot_celo_eas.sql`
- `contracts/src/KokonutResolver.sol`

Common commands:

```bash
python3 -m services.attestation.cli info --chain celo
python3 -m services.attestation.cli schema list
python3 -m services.attestation.cli query --uid 0xATTESTATION_UID --chain celo
```

## Impact Accountability And CIDS

Kokonut targets Common Impact Data Standard (CIDS) v3.2.0 Essential Tier for Green Paper V1. PostgreSQL/Directus remains the canonical data layer; CIDS is an export compatibility layer.

```bash
# Export CIDS Essential Tier JSON-LD for a location
python3 -m services.registry.cids_export --location-id UUID
```

Impact accountability records include `evidence_maturity_level`, `stakeholder_feedback`, `stakeholder_feedback_review`, `stakeholder_outcome`, `impact_claim`, and `metric_proposal`. Public-safe views expose only governed, consented, and eligible records.

See [CIDS Mapping](docs/cids-mapping.md), [Evidence Maturity](docs/evidence-maturity.md), and [Data Dictionary](docs/data-dictionary.md).

## Dashboards Reports And Export

The platform supports Directus partner dashboards, Metabase operational dashboards, refreshable dashboard datasets, deterministic report snapshots, and exports from PostgreSQL or ClickHouse.

```bash
# Refresh dashboard datasets
python3 -m services.export.dataset_refresh --all

# Generate all report types for a location
python3 -m services.export.report_generator --auto --location-id UUID

# Export a collection
python3 -m services.export.exporter --collection expense_event --format csv --output exports/

# Create or use farm activity CSV templates
python3 -m services.export.spreadsheet_bridge --template exports/farm_activity_template.csv
```

Green Paper review dashboards include Evidence Gap and Stakeholder Feedback dashboards under `dashboards/metabase/`. Report snapshots include public-interest context with limitations, evidence gaps, public stakeholder summaries, and public claim readiness signals.

See [Partner Dashboards](docs/partner-dashboards.md), [Export Guide](docs/export-guide.md), and [Reporting Principles](docs/reporting-principles.md).

## Agents Registry And MCP

The registry and agent layer adds Kokonut Common Data Schema records, MRV event metadata, attestation requests, agent capability manifests, agent tasks, agent action logs, and AI summaries while keeping Directus/PostgreSQL as the governed API and data layer.

```bash
# Print a Common Data Schema example
python3 -m services.registry --example-farm-record

# Prepare public/private-hash attestation request metadata
python3 -m services.attestation --subject-type mrv_event --subject-id UUID --event-type mrv_submission --payload-file public.json --private-payload-file private.json

# Print an agent capability manifest example
python3 -m services.agents --example kokonut-mrv-reporter

# List Green Paper agent tasks
python3 -m services.agents.tasks --list

# Run read-only CIDS export agent
python3 -m services.agents.cids_agent --location-id UUID --summary

# Run stakeholder feedback synthesis agent
python3 -m services.agents.feedback_agent --location-id UUID
```

Agent safety is enforced in both PostgreSQL constraints and Directus/Python helpers. Agents can draft, submit, or reject their own outputs, but cannot verify or publish them. High-risk actions such as publishing, attestation submission, financial writes, deletes, and bulk updates are flagged for human approval in `agent_action_log`.

See [Agent Access](docs/agent-access.md) and [PRD Completion Scope](docs/prd-completion.md) for privacy and marketplace boundaries.

## Green Paper V1

Green Paper V1 is a comprehensive 15-section document covering Kokonut's evidence-governed impact intelligence layer for regenerative syntropic farms. It includes system architecture, evidence maturity model, CIDS mapping, stakeholder feedback, agent safety, Web3 verification, carbon and environmental impact, reporting principles, publication boundaries, and pilot data (Kokonut Adelphi).

Green Paper V1 materials should use CIDS Essential Tier exports, public-safe stakeholder summaries, evidence maturity labels, evidence gap dashboards, and public-interest report snapshots. Agent outputs are draft aids for reviewers and operators, not publication authority.

See [Green Paper V1](docs/green-paper-v1.md), [Operator Guide](docs/operator-guide.md), [Reviewer Guide](docs/reviewer-guide.md), and [Agent Workflows](docs/agent-workflows.md).

## Developer Commands

| Task | Command |
|------|---------|
| Start services | `docker compose up -d` |
| Apply schemas/base seeds | `./scripts/seed.sh` |
| Apply pilot data | `./scripts/seed-pilot.sh` |
| Compute verified metrics | `./scripts/compute-metrics.sh` |
| Verify MVP DoD | `./scripts/verify-mvp.sh` |
| Run full local CI | `./scripts/ci-check.sh` |
| Run smoke tests | `python3 -m tests.test_smoke` |
| Run CLI tests | `python3 -m tests.test_cli` |
| Run attestation tests | `python3 -m tests.test_attestation` |
| Run Directus metadata tests | `python3 -m tests.test_directus_metadata` |
| Run CIDS export tests | `python3 -m tests.test_cids_export` |
| Run agent safety tests | `python3 -m tests.test_agent_safety` |
| Run agent task tests | `python3 -m tests.test_agent_tasks` |
| Run portfolio tests | `python3 -m tests.test_portfolio` |
| Run spreadsheet bridge tests | `python3 -m tests.test_spreadsheet_bridge` |
| Run Common Foundations tests | `python3 -m tests.test_common_foundations` |
| Run EBF P0 tests | `python3 -m tests.test_ebf_p0` |
| Run EBF P1 tests | `python3 -m tests.test_ebf_p1` |
| Build Directus hooks | `cd extensions/kokonut-hooks && npm run build` |
| Test Directus hooks | `cd extensions/kokonut-hooks && npm test` |
| Migration status | `python3 -m services.migration status` |
| Apply migrations | `python3 -m services.migration migrate` |
| Build Solidity contracts | `cd contracts && forge build` |
| Test Solidity contracts | `cd contracts && forge test` |

## Repository Layout

```text
config/             Docker, PostgreSQL, ClickHouse, Caddy, and Directus config
contracts/          Foundry project for KokonutResolver and EAS-related contracts
dashboards/         Directus partner dashboard templates and Metabase assets
docs/               Architecture, API, deployment, attestation, agent, and user docs
extensions/         Directus lifecycle hooks, workflow rules, metric hooks, AI helpers
migrations/         Migration tooling and legacy migration helpers
schemas/            PostgreSQL schemas, ClickHouse schemas, Directus snapshots, seeds
scripts/            Setup, seed, schema, metrics, backup, verification, and CI scripts
sdk/                JavaScript/TypeScript and Python SDKs
services/           Python services for ingestion, metrics, analytics, export, agents
tests/              Smoke, CLI, attestation, Directus metadata, and MVP tests
```

## Security And Privacy

- Secrets come from environment variables; do not commit `.env` or private keys.
- Base Compose exposes Caddy only; PostgreSQL and ClickHouse remain internal to Docker networks unless a local override maps ports.
- `PUBLIC_RESTRICT=true` disables unauthenticated public Directus data access.
- Directus rate limiting and login throttling are enabled.
- Public EAS metadata stores hashes, CIDs, UIDs, chain labels, transaction hashes, and timestamps; private evidence remains offchain.
- Public stakeholder feedback requires explicit consent and public-summary scoping; raw stakeholder feedback remains private by default.
- Public carbon claims require Evidence Maturity Level 6 with external verification and methodology reference.
- ClickHouse HTTP insert paths validate interpolated values before SQL construction.
- Agent-generated summaries are drafts and must use approved governed data; agents cannot verify or publish their own outputs.

See [Deployment](docs/deployment.md), [Attestation Guide](docs/attestation-guide.md), and [Agent Access](docs/agent-access.md) for operational security details.

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/user-guide.md) | Role workflows, data entry, lifecycle, dashboards, analytics, export |
| [Architecture](docs/architecture.md) | System overview, data flow, security model |
| [API Reference](docs/api-reference.md) | Directus REST/GraphQL and ClickHouse access notes |
| [OpenAPI Spec](docs/openapi.yaml) | OpenAPI 3.0 API specification |
| [Data Dictionary](docs/data-dictionary.md) | Collections, fields, governed metrics |
| [CIDS Mapping](docs/cids-mapping.md) | CIDS v3.2.0 Essential Tier export mapping |
| [Evidence Maturity](docs/evidence-maturity.md) | Evidence maturity levels and public carbon claim rules |
| [Reporting Principles](docs/reporting-principles.md) | Public-interest reporting principles and report snapshot fields |
| [Stakeholder Feedback](docs/stakeholder-feedback.md) | Feedback consent, privacy, review, and public-summary rules |
| [Participatory Metrics](docs/participatory-metrics.md) | Community-driven metric proposal workflow |
| [Spreadsheet Guide](docs/spreadsheet-guide.md) | CSV import/export templates and validation |
| [Common Foundations Checklist](docs/common-foundations-checklist.md) | Claim quality checklist for useful questions through learning |
| [Agent Safety](docs/agent-safety.md) | Agent approval gates and audit logging |
| [Public Report Disclaimer](docs/public-report-disclaimer.md) | Standard public reporting caveats |
| [Agent Workflows](docs/agent-workflows.md) | Agent task catalogue, output schemas, and safety rules |
| [Operator Guide](docs/operator-guide.md) | Green Paper operator workflow and publishing readiness |
| [Reviewer Guide](docs/reviewer-guide.md) | Human review checklist for claims, feedback, and agent outputs |
| [Green Paper V1](docs/green-paper-v1.md) | Comprehensive 15-section publication-ready document |
| [Deployment](docs/deployment.md) | Docker setup, environment variables, backup, operations |
| [Sandbox](docs/sandbox.md) | Developer sandbox quickstart |
| [Subgraph Guide](docs/subgraph-guide.md) | Subgraph indexer configuration and usage |
| [Attestation Guide](docs/attestation-guide.md) | EAS on Celo, schemas, onchain/offchain attestations, private data |
| [Partner Dashboards](docs/partner-dashboards.md) | Directus/Metabase/custom dashboard options |
| [Agent Access](docs/agent-access.md) | MCP, agent-scoped tokens, permissions, audit logging |
| [Export Guide](docs/export-guide.md) | Data export and report snapshots |

## License

Open source. See [LICENSE](LICENSE).
