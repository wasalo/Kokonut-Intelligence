# Kokonut Intelligence Platform

Open-source intelligence layer for regenerative farm operations, financial performance, ecological outcomes, partner reporting, and Web3 verification.

PostgreSQL and Directus are the canonical schema/API layer. ClickHouse stores analytical events. Python services compute metrics, forecasts, exports, registry payloads, AI summaries, and ingestion jobs. EAS on Celo anchors public verification metadata while private evidence stays offchain.

## Table Of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Local Services](#local-services)
- [Core Capabilities](#core-capabilities)
- [Data Lifecycle And Roles](#data-lifecycle-and-roles)
- [Key Commands](#key-commands)
- [CI And Contributing](#ci-and-contributing)
- [Repository Layout](#repository-layout)
- [Security And Privacy](#security-and-privacy)
- [Documentation](#documentation)
- [License](#license)

## Architecture

| Layer | Technology | Role |
|-------|------------|------|
| Canonical core | PostgreSQL 16 + PostGIS 3.4 + Directus 12.1.1 | Schema, API, permissions, workflows, data entry UI |
| Analytics | ClickHouse 25.8 | Time-series events, high-volume analytical queries, PromQL support |
| BI | Metabase 0.62.4 | Internal dashboards, aggregate reporting, custom visualizations, MCP server |
| Intelligence | Python services | Metrics, forecasts, scoring, exports, ingestion, AI summaries, ML anomaly detection |
| Verification | EAS on Celo + offchain evidence storage | Onchain attestations, offchain signed claims, MRV proof metadata |
| Governance and Guilds | Gnosis Moloch DAO + Colony metadata | Treasury governance, Guild contribution records, reputation snapshots |
| Contracts | Foundry + Solidity | KokonutResolver attester gating for EAS schemas |
| Workflow | Prefect 3.x | Pipeline orchestration with event-driven automations |
| External API | gRPC (port 50051) + Protobuf | Type-safe external API with streaming, API key auth, Buf codegen |

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

# 4. Compute draft, unverified governed metric values
./scripts/compute-metrics.sh

# 5. Have a human reviewer verify each accepted value
python3 -m services.metrics --verify-value METRIC_VALUE_UUID \
  --verified-by REVIEWER_UUID --verification-notes "Reviewed evidence"

# 6. Verify the MVP definition of done
./scripts/verify-mvp.sh
```

Or using Make targets:

```bash
make seed          # applies schema + base seeds
make ci            # runs the full local CI suite
make test          # runs pytest over all tests
make lint          # ruff lint check
make typecheck     # mypy type check
make fmt           # ruff format
make forge-test    # Solidity tests
make hooks-test    # Directus hooks tests
```

Run the full local check with `./scripts/ci-check.sh` or `make ci`. For sandbox-specific setup, see [Developer Sandbox](docs/sandbox.md). For deployment guidance, see [Deployment](docs/deployment.md).

## Local Services

Base `docker-compose.yml` exposes Caddy and gRPC on the host, binds Directus and MQTT to loopback, and keeps PostgreSQL, ClickHouse, and Metabase private. The optional worker overlay joins the private database network without turning metric computation into a persistent service.

| Service | Base URL | Notes |
|---------|----------|-------|
| Caddy | `https://localhost` | TLS termination, reverse proxy, security headers |
| Directus API | `https://localhost/directus` | Canonical API and data access |
| Directus admin | `https://localhost/admin` | Admin UI and data entry |
| Directus direct | `http://127.0.0.1:8055` | Loopback-only API/admin access in base Compose |
| Metabase | `https://localhost/metabase` | BI dashboards |
| gRPC | `localhost:50051` | Host-exposed external API in base Compose; removed by the production overlay |
| MQTT | `mqtt://127.0.0.1:1883` | Loopback-only sensor broker |
| PostgreSQL | Docker service `database:5432` | Canonical data store; use `docker compose exec database ...` |
| ClickHouse | Docker service `clickhouse:8123` | Analytical store; use Docker network or `docker compose exec clickhouse ...` |
| Worker | Compose service `kokonut-worker` | Cron/one-shot Python execution; `compute-metrics.sh` uses an ephemeral `run --rm` worker when the Compose database is running |

The default local override may expose Metabase at `http://localhost:3001`. Use direct service URLs only when the effective Compose configuration maps them.

## Core Capabilities

- **Governed farm operations**: Activities, harvests, sales, expenses, losses, labor, field notes, inventory, maintenance, revenue events, and partner-scoped access through Directus.
- **Intelligence and analytics**: Versioned metric definitions, scenario forecasts, Fortune 500-style farm scoring, ecological analytics, revenue multiplier opportunity maps, EBF scorecards with trust graphs, portfolio messy roll-ups, and AI-generated summaries.
- **Impact accountability and evidence**: Evidence maturity levels, stakeholder feedback, impact claims, participatory metric proposals, holistic well-being, financial resilience, capital efficiency, commons liberation, GNH alignment, regenerative outcomes, open-source scaling, commons governance, bio-factory operations, and CIDS Essential Tier JSON-LD export.
- **Web3 verification**: EAS schemas on Celo, KokonutResolver attester gating, onchain/offchain attestations, private evidence hashes, wallet activity, Gnosis DAO metadata, and public attestation summaries.
- **Governance and guilds**: Colony-backed Guild metadata, contribution records, reputation snapshots, anti-capture governance, flexible redistribution, federation protocols, and DAO proposal links while Gnosis Moloch remains the treasury governance layer.
- **Agent ecosystem**: Agent identities with capability manifests, tasks, action logs, AI summaries, and scoped MCP/Directus access. Agents can draft and submit but cannot verify, publish, attest, or score. Contract identity, payments, escrow, and marketplace logic remain external to this repo.
- **Organic certification readiness**: Organic compliance records for transition tracking, input audit, buffer zones, harvest segregation, and composite readiness scoring (0-100).
- **True Cost Accounting**: Hidden cost tracking, natural/social capital valuation, life cycle assessment, GRI indicator mapping, and cross-capital flow analysis for triple bottom line reporting.
- **Silvi tree-tracking integration**: Individual tree GPS tracking, growth rate analytics, GeoJSON/KML/XML export, spatial clustering, pest hotspots, canopy analysis, and habitat connectivity scoring.
- **Emergency response**: Incident tracking with response actions, recovery timelines, and lessons learned for crisis resilience.
- **CRISP risk scoring**: Five-dimension risk scoring (carbon yield, climate, policy, financial, implementation) with configurable per-location weights and AAA-D composite rating.
- **Abundance Protocol integration**: Impact estimate posts, 3-tier validation with quadratic voting, tokenized carbon credits with auto-adjustment, and incentive alignment tracking.
- **Digital Soil Mapping**: XGBoost-based SOC prediction with spectral indices, time-series features, and geographic cross-validation.
- **dMRV architecture**: Automated satellite data collection (GEE/Copernicus), real-time IoT ingestion (MQTT/HTTP), ML anomaly detection (Prophet + Isolation Forest), and EAS on-chain verification.
- **Field data collection**: Detailed SOPs for soil sampling, tree measurement, biodiversity surveys, water sampling, harvest recording, and pest monitoring with measurement cadence matrix.
- **Oracle infrastructure**: Multi-source price feeds with median consensus, real-time commodity futures, and actuator command dispatch.
- **Data Stream**: Chronological project data posts with Markdown content, file attachments (Directus + URLs), geo-tagged files, full-text search, blockchain anchoring via EAS, and visibility controls.
- **Ecocredit module**: Credit class/batch hierarchy, basket with token deposits, marketplace with escrow, per-account balance tracking, bridge operations, project enrollment workflow, and retirement certificates.
- **Platform integrity**: Ordered, checksummed PostgreSQL migrations reject drift; the API gateway defaults unknown routes to authenticated access; durable scheduler leases/runs and event outbox/dead-letter handling support safe retries and operator recovery.
- **Credit custody and retirement**: Ledger-backed balances preserve account and batch custody, while carbon retirement reserves quantity atomically, requires separate human confirmation, and generates certificates only from governed retirement records.
- **Threatcasting and backcasting**: Threats, warning signals, cross-impact and cascade analysis feed future narratives, horizons, backcast milestones, sustainability-principle alignment, assumption challenges, and comparable pathways.
- **Real-time Delphi**: Roundless, pseudonymous panel consultation provides weighted consensus and stability tracking; facilitator outputs remain drafts and recommendations require human approval.
- **Linked data infrastructure**: IRI system with versioning, RDF triple store, SPARQL queries, content-addressed storage, resolver registry, and evidence chaining.
- **Schema.org alignment**: All LinkML schemas mapped to schema.org URIs via slot_uri, JSON-LD context generation, and `@graph` support for complex documents.
- **Regen Network parity**: Full alignment with Regen Data Standards (ClaimType, VerificationStatus, VerdictType enums), CreditClassInfo, ProjectInfo, ProjectPost schemas, and Data module v2 concepts.
- **ARKIV parity**: Time-scoped data (expires_at), origin transaction indexing for double-mint prevention, and marketplace fee collection/distribution.
- **GeoNode parity**: Shapefile import (fiona), KML import, raster metadata, CSW OGC Catalogue Service, ISO 19115 metadata fields, hierarchical thesaurus system, interactive Leaflet map viewer, geostories, and general harvesting framework.
- **gRPC API**: Type-safe external API with Protobuf schemas, server-side streaming (5s batching), API key authentication, Buf codegen for Python/TypeScript, and gRPC-web support.

## How Metrics Enable Answers

The platform combines governed metrics, analytics functions, agents, and report types to answer questions across six tiers:

| Tier | Collective Question | Example Answer |
|------|-------------------|----------------|
| **Foundation** | "What is the financial and operational baseline?" | "$12K baseline → $24.5K current (2x). Soil carbon +14%. Species +75%." |
| **Governance** | "Can we trust the data?" | "All metrics versioned, evidence-gated, and exposed through governed views." |
| **Frameworks** | "Are we actually making a difference?" | "EBF 7.2/10. 57.5 tCO2e sequestered. 37 species. Blockchain-verifiable claims." |
| **Wellbeing** | "Are people and communities thriving?" | "GNH 78/100. 91.6% tree survival. 36 training hours. Anti-capture governance." |
| **Operations** | "Can we scale regeneratively?" | "72.5/100 organic readiness. 64% training improvement. $25K grants awarded." |
| **True Cost** | "What is the full triple-bottom-line picture?" | "Market profit $9,200. True profit $20,533 (after hidden costs + capital values)." |

See [Metrics by Development Phase](docs/metrics-by-phase.md) for the complete mapping of phases, metrics, and collective insights.

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

## Key Commands

`AGENTS.md` is the canonical command reference for all local commands — CLI flags, analytics, ingestion, agents, report types, and tests. Below are the most common entry points:

```bash
# Metrics
python3 -m services.metrics --list
python3 -m services.metrics --compute --all-locations
python3 -m services.metrics --verify-value METRIC_VALUE_UUID --verified-by REVIEWER_UUID --verification-notes "Reviewed evidence"

# Reports (use --auto for all registered types)
python3 -m services.export.report_generator --auto --location-id UUID
python3 -m services.export.report_generator --type climate_impact --location-id UUID

# CIDS export
python3 -m services.registry.cids_export --location-id UUID

# Agents (see AGENTS.md for the full list)
python3 -m services.agents.tasks --list
python3 -m services.agents.ai_summary --location-id UUID --summary-type combined

# Attestation
python3 -m services.attestation.cli info --chain celo
python3 -m services.attestation.cli schema list

# Migration
python3 -m services.migration status
python3 -m services.migration migrate
```

See [AGENTS.md](AGENTS.md) for the full command catalogue and [CHANGELOG.md](CHANGELOG.md) for release history.

## CI And Contributing

CI runs 3 jobs on every push and pull request via `.github/workflows/ci.yml`:

| Job | What it checks |
|-----|----------------|
| Python checks | Ruff lint, full `ci-check.sh` suite, CLI smoke tests, attestation tests, integration tests |
| Directus hooks | `npm ci`, `npm run build`, `npm test` in `extensions/kokonut-hooks` |
| Foundry contracts | `forge fmt --check`, `forge build --sizes`, `forge test -vvv` |

Branch protection is enforced via GitHub rulesets on `main`:
- Pull requests required (1 approval, code owner review, review thread resolution)
- Required status checks: Python checks, Directus hooks, Foundry contracts
- Linear history enforced; force pushes and deletions blocked
- Version tags (`v*`) protected from force pushes and deletions

Contributing guidelines:
- `AGENTS.md` is the canonical command reference — update it when adding commands, env vars, or conventions.
- `.github/CODEOWNERS` defines review ownership; sensitive paths require admin review.
- `.github/pull_request_template.md` includes a checklist for CI, secrets, schema idempotency, agent registration, and public views.
- `.github/dependabot.yml` enables weekly dependency updates for pip, npm, and github-actions.
- Seed files must be idempotent with `ON CONFLICT` guards and `psql -v ON_ERROR_STOP=1`.

## Production Deployment

```bash
# With built-in Caddy (default)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# With external Traefik (VPS already running Traefik)
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.traefik.yml up -d

# With worker container for cron-based ingestion
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.worker.yml --profile worker up -d
```

Health monitoring with alerting:

```bash
# Manual health check
./scripts/health-check.sh

# JSON output for external monitoring
./scripts/health-check.sh --json

# Cron wrapper (quiet on success, alerts on failure)
*/5 * * * * /opt/Kokonut-Intelligence/scripts/health-alert.sh
```

See [Deployment](docs/deployment.md) for full production setup, reverse proxy options, worker container, monitoring, and a production checklist.

## Repository Layout

```text
config/             Docker, PostgreSQL, ClickHouse, Caddy, Directus, Mosquitto, and worker crontab config
contracts/          Foundry project for KokonutResolver and EAS-related contracts
dashboards/         Metabase dashboard templates with backing SQL
docs/               Guides and references; see Documentation below
extensions/         Directus lifecycle hooks, workflow rules, metric hooks, AI helpers
migrations/         Migration tooling and legacy migration helpers
schemas/            PostgreSQL and ClickHouse schemas, Directus snapshots, seed files
scripts/            Setup, seed, schema, metrics, backup, health-check, and CI scripts
sdk/                JavaScript/TypeScript and Python SDKs
services/           Python services for ingestion, metrics, analytics, export, agents, attestation, scoring, abundance, flows, data_stream, credit_class, iri, rdf, data_module, certificates, metadata_api, linkml, csw, geostory, maps, thesaurus, grpc
tests/              Unit and integration tests for platform services and invariants
Dockerfile.worker   Optional worker container for cron-based ingestion
docker-compose.yml  Base services (PostgreSQL 16, ClickHouse 25.8, Directus 12.1.1, Metabase 0.62.4, Caddy, Mosquitto)
docker-compose.prod.yml     Production overlay (resource limits, no direct port exposure)
docker-compose.traefik.yml  Traefik overlay (disables Caddy, adds Traefik labels)
docker-compose.worker.yml   Worker overlay (cron-based Python ingestion container)
```

## Security And Privacy

- Secrets come from environment variables; do not commit `.env` or private keys. See `.env.example` for the current catalog and placeholder warnings.
- Base Compose keeps PostgreSQL and ClickHouse internal, binds Directus and MQTT to loopback, and exposes Caddy plus gRPC. The production overlay removes direct application-service exposure.
- `PUBLIC_RESTRICT=true` disables unauthenticated public Directus data access.
- Directus rate limiting and login throttling are enabled.
- Public EAS metadata stores hashes, CIDs, UIDs, chain labels, transaction hashes, and timestamps; private evidence remains offchain.
- Public stakeholder feedback requires explicit consent and public-summary scoping; raw stakeholder feedback remains private by default.
- Public carbon claims require Evidence Maturity Level 6 with external verification and methodology reference.
- ClickHouse HTTP insert paths validate interpolated values before SQL construction.
- Agent-generated summaries are drafts and must use approved governed data; agents cannot verify or publish their own outputs.

See [Deployment](docs/deployment.md), [Attestation Guide](docs/attestation-guide.md), and [Agent Access](docs/agent-access.md) for operational security details.

## Documentation

Documentation lives under `docs/`. Key entry points:

| Document | Description |
|----------|-------------|
| [User Guide](docs/user-guide.md) | Role workflows, data entry, lifecycle, dashboards, analytics, export |
| [Architecture](docs/architecture.md) | System overview, data flow, security model |
| [Platform Integrity](docs/platform-integrity.md) | Cross-cutting integrity boundaries and operational guarantees |
| [Migrations](docs/migrations.md) | Ordered migration execution, checksums, drift detection, and recovery |
| [Gateway](docs/gateway.md) | Route policy, authentication, default-deny behavior, rate limits, and audit |
| [Metric Verification](docs/metric-verification.md) | Draft computation, independent human verification, and public exposure |
| [Scheduler and Events](docs/scheduler-and-events.md) | Durable scheduler runs, event processing, retries, and dead-letter recovery |
| [Credit Lifecycle](docs/credit-lifecycle.md) | Issuance, custody, balances, retirement review, and certificates |
| [Threatcasting and Backcasting](docs/threatcasting-and-backcasting.md) | Threat intelligence, future narratives, principles, and pathway planning |
| [Delphi](docs/delphi.md) | Real-time Delphi studies, consensus, facilitation, and approval boundaries |
| [API Reference](docs/api-reference.md) | Directus REST/GraphQL and ClickHouse access notes |
| [Data Dictionary](docs/data-dictionary.md) | Collections, fields, governed metrics |
| [Metrics by Development Phase](docs/metrics-by-phase.md) | Which metrics each phase enables, how they're measured, and collective insights |
| [AGENTS.md](AGENTS.md) | Canonical command reference (CLI, analytics, ingestion, agents, tests) |
| [CHANGELOG.md](CHANGELOG.md) | Release history and unreleased changes |
| [Green Paper V1](docs/green-paper-v1.md) | Comprehensive 15-section publication-ready document |
| [Export Guide](docs/export-guide.md) | Report types, data exports, and report snapshots |
| [EBF Scorecard Guide](docs/ebf-scorecard.md) | EBF pillars, rubric, scorecards, trust graphs |
| [Attestation Guide](docs/attestation-guide.md) | EAS on Celo, schemas, onchain/offchain attestations |
| [Deployment](docs/deployment.md) | Docker setup, environment variables, backup, operations |
| [Agent Access](docs/agent-access.md) | MCP, agent-scoped tokens, permissions, audit logging |
| [Agent Workflows](docs/agent-workflows.md) | Agent task catalogue, output schemas, and safety rules |
| [Evidence Maturity](docs/evidence-maturity.md) | Evidence maturity levels and public carbon claim rules |
| [Reporting Principles](docs/reporting-principles.md) | Public-interest reporting principles and report snapshot fields |
| [Data Stream](docs/data-stream.md) | Chronological data posts, file attachments, blockchain anchoring |
| [gRPC API](docs/grpc-api.md) | Type-safe external API, streaming, Protobuf schemas |
| [Dependency Capabilities](docs/dependency-capabilities.md) | All dependency updates mapped to platform capabilities |

Additional docs cover: CIDS mapping, stakeholder feedback, participatory metrics, holistic well-being, financial sustainability, risk mitigation, scaling roadmap, capital efficiency, commons liberation, GNH alignment, regenerative outcomes, open-source capitalist scaling, commons governance, EBF trust graph, spreadsheet guide, common foundations checklist, agent safety, public report disclaimer, operator guide, reviewer guide, advisor review guide, PRD completion scope, partner dashboards, sandbox, subgraph guide, EBF implementation memo, CRISP risk scoring, dMRV architecture, field data collection guide, telemetry infrastructure, ecological modeling, and OpenAPI spec (`docs/openapi.yaml`).

## License

Open source. See [LICENSE](LICENSE).
