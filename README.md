# Kokonut Intelligence Platform

Open-source intelligence layer for regenerative farm operations, financial performance, ecological outcomes, partner reporting, and Web3 verification.

PostgreSQL and Directus are the canonical schema/API layer. ClickHouse stores analytical events. Python services compute metrics, forecasts, exports, registry payloads, AI summaries, and ingestion jobs. EAS on Celo anchors public verification metadata while private evidence stays offchain. Eleven Solidity contracts power the Guild protocol, credit token, price oracle, selective disclosure, and EAS resolver on Gnosis Mainnet.

## Table Of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Local Services](#local-services)
- [Core Capabilities](#core-capabilities)
- [On-Chain Deployments](#on-chain-deployments)
- [How Metrics Enable Answers](#how-metrics-enable-answers)
- [Data Lifecycle And Roles](#data-lifecycle-and-roles)
- [Key Commands](#key-commands)
- [CI And Contributing](#ci-and-contributing)
- [Repository Layout](#repository-layout)
- [Security And Privacy](#security-and-privacy)
- [Documentation](#documentation)
- [License](#license)

---

## Architecture

| Layer | Technology | Role |
|-------|------------|------|
| Canonical core | PostgreSQL 16 + PostGIS 3.4 + Directus 12.1.1 | Schema, API, permissions, workflows, data entry UI |
| Analytics | ClickHouse 25.8 | Time-series events, high-volume analytical queries, PromQL support |
| Cache | Redis 7 | Directus caching, rate limiting, session store |
| BI | Metabase 0.62.4 | Internal dashboards, aggregate reporting, custom visualizations, MCP server |
| Intelligence | Python services | Metrics, forecasts, scoring, exports, ingestion, AI summaries, ML anomaly detection |
| Verification | EAS on Celo + offchain evidence storage | Onchain attestations, offchain signed claims, MRV proof metadata |
| Governance and Guilds | Gnosis Moloch DAO + Colony metadata | Treasury governance, Guild contribution records, reputation snapshots |
| Contracts | Foundry + Solidity (11 contracts) | Guild protocol, Credit Token, Price Oracle, Selective Disclosure, EAS Resolver |
| MQTT | Mosquitto 2 | TLS sensor broker for IoT ingestion |
| Systems Intelligence | Python services | Trend analysis, geostatistics, systems thinking, process mining, causal loops, stock-and-flow simulation |
| Organizational | Python services | Work items, escalation, budgets, objectives, portfolio, S&OP, capability maps, strategy execution |
| Workflow | Prefect 3.x | Pipeline orchestration with event-driven automations |
| External API | gRPC (port 50051) + Protobuf | Type-safe external API with streaming, API key auth, Buf codegen |

See [Architecture](docs/architecture.md) for system design, data flow, and security model details.

---

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

# 6. Verify the platform definition of done
./scripts/verify-platform.sh
```

> [!TIP]
> Run `make ci` to execute the full local CI suite in one command. It applies seeds, runs all tests, and performs lint checks.

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

---

## Local Services

Base `docker-compose.yml` exposes Caddy and gRPC on the host, binds Directus, gateway, and MQTT to loopback, and keeps PostgreSQL, ClickHouse, Redis, and Metabase private. The optional worker overlay joins the private database network without turning metric computation into a persistent service.

| Service | Base URL | Notes |
|---------|----------|-------|
| Caddy | `https://localhost` | TLS termination, reverse proxy, security headers |
| Field Collector | `https://localhost/mobile` | Offline-first companion; LAN phones use `https://<lan-ip>/mobile` |
| Directus API | `https://localhost/directus` | Canonical API and data access |
| Directus admin | `https://localhost/admin` | Admin UI and data entry |
| Directus direct | `http://127.0.0.1:8055` | Loopback-only API/admin access in base Compose |
| Gateway | `http://127.0.0.1:8099` | FastAPI gateway (mobile API); Caddy proxies `/mobile` and `/api/mobile/*` |
| Metabase | `https://localhost/metabase` | BI dashboards |
| gRPC | `localhost:50051` | Host-exposed external API in base Compose; removed by the production overlay |
| MQTT | `mqtts://127.0.0.1:8883` | Loopback-only TLS sensor broker |
| PostgreSQL | Docker service `database:5432` | Canonical data store; use `docker compose exec database ...` |
| ClickHouse | Docker service `clickhouse:8123` | Analytical store; use Docker network or `docker compose exec clickhouse ...` |
| Worker | Compose service `kokonut-worker` | Cron/one-shot Python execution; `compute-metrics.sh` uses an ephemeral `run --rm` worker when the Compose database is running |

The default local override may expose Metabase at `http://localhost:3001`. Use direct service URLs only when the effective Compose configuration maps them.

### Field Collector on the LAN

```bash
docker compose up -d --build gateway caddy
# Phone on the same Wi‑Fi:
#   https://<host-lan-ip>/mobile
```

Caddy terminates TLS and proxies `/mobile` and `/api/mobile/*` to the gateway.
Full deploy steps (local, production Caddy, Traefik) are in
[Deployment — Field Collector](docs/deployment.md#field-collector-mobile-lan-access).

---

## Core Capabilities

| Category | Capability | Key Components |
|----------|------------|----------------|
| **Farm Operations** | Governed farm operations | Activities, harvests, sales, expenses, losses, labor, field notes, inventory, maintenance, revenue events, partner-scoped access via Directus |
| | Precision agriculture | Yield monitoring with prediction/benchmarking, precision irrigation with zone management and water-balance, digital twin crop simulation, nutrient budget tracking, mobile offline-first collection |
| | Traceability | Batch tracking with custody chain, quality testing, food safety, cold chain monitoring, forward/backward tracing |
| | Extension & peer learning | Learning modules, peer groups, delivery tracking, assessment effectiveness |
| | Farmer identity & cooperatives | Profiles with credentials/KYC, role-based access, device registration, cooperative membership, asset booking, purchase aggregation, collective market orders |
| | Energy, waste & landscape | Energy source monitoring with efficiency/carbon intensity, waste recording with composting/incident tracking, habitat/corridor management, hedgerow recording, buffer compliance, pollinator health |
| **Intelligence** | Metrics & analytics | Versioned metric definitions, scenario forecasts, Fortune 500-style farm scoring, ecological analytics, revenue multiplier opportunity maps, EBF scorecards with trust graphs, AI-generated summaries |
| | Trend analysis & geostatistics | Least-squares estimation, Mann-Kendall significance, exponential smoothing, seasonal decomposition, CUSUM/PELT change-point detection, ARIMA forecasting, variogram modeling, kriging, sequential Gaussian simulation, spatial cross-validation |
| | Systems thinking | Causal loop diagrams, leverage point identification, system archetypes, double-loop learning, time delay tracking, stock-and-flow simulation, mental model elicitations |
| | OODA loop & adaptive decisions | Observe→Orient→Decide→Act cycle with situation assessment, adaptive thresholds, decision policy engine, cycle tracking, human-approval gateways |
| | Process intelligence | Process mining (variant discovery, conformance checking, cycle-time analysis), predictive BPM with SLA breach forecasting, SPC charts, CTQ analysis, process health dashboards |
| | Process architecture & costing | Process architecture mapping, interface definitions, target setting, simulation, gap analysis, service catalog, process costing |
| **Impact & Evidence** | Impact accountability | Evidence maturity levels, stakeholder feedback, impact claims, participatory metric proposals, holistic well-being, financial resilience, capital efficiency, commons liberation, GNH alignment, regenerative outcomes, CIDS Essential Tier JSON-LD export |
| | CRISP risk scoring | Five-dimension risk scoring (carbon yield, climate, policy, financial, implementation) with configurable per-location weights and AAA-D composite rating |
| | Organic certification readiness | Organic compliance records for transition tracking, input audit, buffer zones, harvest segregation, composite readiness scoring (0-100) |
| | True cost accounting | Hidden cost tracking, natural/social capital valuation, life cycle assessment, GRI indicator mapping, cross-capital flow analysis |
| | Emergency response | Incident tracking with response actions, recovery timelines, lessons learned |
| **Web3 & Verification** | EAS on Celo | KokonutResolver attester gating, onchain/offchain attestations, private evidence hashes, public attestation summaries, 4 registered schemas |
| | Ecocredit module | Credit class/batch hierarchy, basket with token deposits, marketplace with escrow, per-account balance tracking, bridge operations, project enrollment, retirement certificates |
| | Credit custody & retirement | Ledger-backed balances preserving account/batch custody, atomic retirement with human confirmation, governed certificate generation |
| | Linked data infrastructure | IRI system with versioning, RDF triple store, SPARQL queries, content-addressed storage, resolver registry, evidence chaining |
| | Data Stream | Chronological project data posts with Markdown content, file attachments, geo-tagged files, full-text search, blockchain anchoring via EAS |
| **Governance** | Governance framework abstraction | Pluggable `GovernanceFramework` adapters; Moloch v3 (Baal) on Gnosis for proposals, votes, members, shamans; future: OpenZeppelin Governor, Aragon, Colony |
| | Governance circles & roles | Holacracy-inspired circles, role authority, tension tracking, proposals, tactical coordination, cockpit dashboards |
| | Stakeholder ecosystem | Stakeholder foundation, consent management, identity resolution, engagement plans, grievance handling, representation metrics, decision lineage, trust evidence with timeline |
| | Threatcasting & backcasting | Threats, warning signals, cross-impact/cascade analysis, future narratives, horizons, backcast milestones, sustainability-principle alignment, assumption challenges, comparable pathways |
| | Real-time Delphi | Roundless pseudonymous panel consultation, weighted consensus, stability tracking; facilitator outputs are drafts, recommendations require human approval |
| **Strategy & Planning** | Strategy system | Strategy plans, choices, assumptions, investments, allocation, coherence, execution snapshots, governance reporting, integrity gates, risk evidence, portfolio selection, contingencies, consultation, foresight frames |
| | Competitive landscape | Competitive analysis, strategic positioning, advantage assessment, advantage outcomes, customer value analysis, competitive monitoring |
| | Management workflow | Work items with SLA tracking, responsibility assignments, escalation sweeps, capacity-aware organizational planning |
| | Planning & budgeting | Budgets with variance analysis, objectives with KPIs, portfolio management (programs and projects), S&OP cockpit |
| | Business architecture | Capability maps, strategy maps with initiative tracking, vision/mission governance, formal value stream definitions |
| | Pitch & business planning | Pitch deck generation with evidence backing, elevator pitches, business plan generation, template-based BMCs |
| **Coordination** | Coordination & alliance system | Alliance management, coordination workflows, learning accounting, governance cockpit, trigger safety, integrity controls |
| | Solution lifecycle | Solution experiments, funding tracking, adoption metrics, scale/learning/retirement stages, sequential gate integrity |
| | Sequential evidence & decisions | Sequential evidence ledger, decision engine, experiment analysis, odds calculation, decision integrity controls |
| | Operating pilot | Capacity-aware planning, work selection claims, competencies/learning tracking, coaching/resources, dual-scope operating pilot |
| **Agents & AI** | Agent ecosystem | Agent identities with capability manifests, tasks, action logs, AI summaries, scoped MCP/Directus access; agents can draft/submit but cannot verify/publish/attest/score |
| | Unified meta-CLI | Single `python3 -m services.cli` entry point aggregating all service CLIs; legacy per-service invocations remain supported |
| | dMRV architecture | Automated satellite data collection (GEE/Copernicus), real-time IoT ingestion (MQTT/HTTP), ML anomaly detection (Prophet + Isolation Forest), EAS on-chain verification |
| | Digital soil mapping | XGBoost-based SOC prediction with spectral indices, time-series features, geographic cross-validation |
| **Smart Contracts** | Guild protocol | Registry, Domain, TaskBoard, EvidenceReview, Governance, Points, UpgradeTimelock — all deployed on Gnosis Mainnet |
| | Credit Token | ERC-20 with burning, pausing, and role-based access; deployed behind ERC1967 proxy |
| | Price Oracle | On-chain price feeds with emergency updater role; deployed behind ERC1967 proxy |
| | Selective Disclosure | Privacy-preserving attestation gating; deployed behind ERC1967 proxy |
| | KokonutResolver | EAS attester gating for registered schemas on Celo |
| **Platform** | Platform integrity | Ordered checksummed PostgreSQL migrations reject drift; API gateway defaults unknown routes to authenticated access; durable scheduler leases and event outbox/dead-letter handling |
| | Strategic reserve | Monitorable reserve registry (carbon buffer, commons reserve, financial ring-fence, capability standby, seed vault) with adequacy, drawdown headroom, trigger/breach status; release proposals are DRAFT-only and human-approved |
| | Capital accounting | Dynamic 8 Forms of Capital inventory, Keynes-inspired deferred-credit ledger, capacity assessment, consumption-vs-reinvestment diversion, value-capture risk diagnostics |
| | Tactical layer & simulation | Chess-inspired governance tactics (fork, pin, zwischenzug, double-check, promotion ladder), Monte Carlo perturbation, CRT-style clash resolution |
| | Data governance | Consent management, access logging, data portability, retention policies, sharing agreements with audit trails |
| | Platform upgrade system | Timelock-gated upgrade authority, staged deployment with temporary upgrader handoff, upgrade verification scripts |
| **Field Data** | Field data collection | Detailed SOPs for soil sampling, tree measurement, biodiversity surveys, water sampling, harvest recording, pest monitoring with measurement cadence matrix |
| | Silvi tree tracking | Individual tree GPS tracking, growth rate analytics, GeoJSON/KML/XML export, spatial clustering, pest hotspots, canopy analysis, habitat connectivity scoring |
| | Oracle infrastructure | Multi-source price feeds with median consensus, real-time commodity futures, actuator command dispatch |
| **Business** | Revenue model & channels | Revenue streams, pricing strategies, cost structures, break-even analysis, sensitivity analysis, multi-channel orchestration (SMS, WhatsApp, mobile app, email), partner lifecycle |
| | Environmental scanning | Multi-step PESTEL analysis, regional readiness assessments with benchmarks, public and segment mapping, demand analysis |
| | Marketplace | Listings, orders, price trends, cooperative market orders |
| **Regulatory** | Abundance Protocol | Impact estimate posts, 3-tier validation with quadratic voting, tokenized carbon credits with auto-adjustment, incentive alignment tracking |
| | Schema.org alignment | All LinkML schemas mapped to schema.org URIs, JSON-LD context generation, `@graph` support |
| | Regen Network parity | ClaimType, VerificationStatus, VerdictType enums, CreditClassInfo, ProjectInfo, ProjectPost schemas, Data module v2 concepts |
| | ARKIV parity | Time-scoped data (expires_at), origin transaction indexing, marketplace fee collection/distribution |
| | GeoNode parity | Shapefile/KML import, raster metadata, CSW OGC Catalogue Service, ISO 19115 metadata, hierarchical thesaurus, Leaflet map viewer, geostories |
| **External** | gRPC API | Type-safe external API with Protobuf schemas, server-side streaming (5s batching), API key auth, Buf codegen for Python/TypeScript, gRPC-web support |
| | Business Model Canvas | 1-click BMC derivation from canonical tables; comprehensive status composing 13 per-location sections plus network-wide rollup |
| | State of Kokonut | Ecosystem report across locations with ecosystem-actor funding view; Mermaid + JSON visual timelines (ecosystem tree, Ikigai, farm phases, crop timelines) |

> [!NOTE]
> Agents can draft and submit governed records but **cannot** verify, publish, attest, or score. Contract identity, payments, escrow, and marketplace logic remain external to this repository.

---

## On-Chain Deployments

### Gnosis Mainnet (Chain ID 100)

All contracts are verified on GnosisScan. Deployment records live in `contracts/broadcast/*/100/run-latest.json`.

| Contract | Address |
|----------|---------|
| Guild Registry | `0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad` |
| Guild Domain | `0x45dC48FEC5f145020bB84e7d39bc4B2FED166d01` |
| Task Board | `0x2319bc674eeA617990bc40e44a98b6856C358801` |
| Evidence Review | `0x48Ae65bed10d8F9B6E952bb7091c14CCe9AB64De` |
| Guild Governance | `0x9aEBAbF4e85b831aDba53eE62eA939A22b93F4fc` |
| KGP proxy | `0x136247fCad81c4BE6560754AF440D7B1A320516f` |
| KGP upgrade timelock | `0xefAeF01B3DDeF2041A1dbdCEbcA352eD2240920A` |
| Credit Token proxy | `0x26Cc52596279D568e7A340DB16e1E24eFa5b95d3` |
| Selective Disclosure proxy | `0x964b0d0B02965654491e9F8265772165B8fE4562` |
| Price Oracle proxy | `0xA6D24A665FB2f41C07c54b145034576e9BC6826a` |

> [!IMPORTANT]
> The KGP upgrade timelock enforces a **48-hour delay** (`172800s`) on all implementation upgrades. The `UPGRADER_ROLE` is self-administered — only the timelock holder can grant/revoke it.

See [Gnosis Mainnet Deployment](docs/gnosis-mainnet-deployment.md) for full addresses, transactions, authority matrix, and verification status.

### Celo Mainnet (Chain ID 42220)

| Schema | UID | Purpose |
|--------|-----|---------|
| `kokonut-mrv` | `0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54` | MRV claims (location, crop, quantity, evidence) |
| `kokonut-impact` | `0xb99bb4b2a55218b8f4df1f0bd4c39400711809f13ef5d150d2903648c6590dfe` | Environmental impact (soil carbon, biodiversity, NDVI) |
| `kokonut-financial` | `0x75b42beb85dd852134dfaff3de41b8dc361ed0cb2bf93ce3009c8ec082de905b` | Financial summaries (NOI, revenue, costs) |
| `kokonut-harvest` | `0xb359f9756e3cb3597e4048dccae2842083359906fbae8dc8c0e9af8ac1b3ccff` | Harvest verification (quantity, quality, date) |
| `kokonut-compliance` | `0x59632edcf1d04be0c2dcfd572282bbd4dac518e7a92872ec45ade29876ef95f5` | Partner compliance and audit trails |
| `kokonut-data-post` | `0xf0de37f5c4a441aedb794d5585201c6ef150543dc53f894e1212f7e330205045` | Data stream posts for environmental project tracking |

See [Attestation Guide](docs/attestation-guide.md) for schema details and registration flow.

---

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

---

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

---

## Key Commands

> [!NOTE]
> `AGENTS.md` is the canonical command reference for all local commands — CLI flags, analytics, ingestion, agents, report types, and tests. The examples below are the most common entry points.

```bash
# Unified meta-CLI (aggregates all service CLIs)
python3 -m services.cli --help
python3 -m services.cli metrics --list

# Metrics
python3 -m services.metrics --list
python3 -m services.metrics --compute --all-locations
python3 -m services.metrics --verify-value METRIC_VALUE_UUID --verified-by REVIEWER_UUID --verification-notes "Reviewed evidence"

# Reports (use --auto for all registered types; --all spans every location)
python3 -m services.export.report_generator --auto --all
python3 -m services.export.report_generator --type climate_impact --location-id UUID

# Network-level reports (--all, or repeat --location-id to select several)
python3 -m services.export.report_generator --type state_of_kokonut --all
python3 -m services.export.report_generator --type state_of_kokonut_graphs --all
python3 -m services.export.report_generator --type comprehensive_status --location-id UUID
python3 -m services.export.report_generator --type strategic_reserve --all
python3 -m services.export.report_generator --type dao_proposal_history

# CIDS export
python3 -m services.registry.cids_export --location-id UUID

# Agents (see AGENTS.md for the full list)
python3 -m services.agents.tasks --list
python3 -m services.agents.ai_summary --location-id UUID --summary-type combined

# Attestation
python3 -m services.attestation.cli info --chain celo
python3 -m services.attestation.cli schema list

# OODA and decisions
python3 -m services.decision.policies --list
python3 -m services.decision.policies --evaluate --location-id UUID
python3 -m services.orientation.assess  # situation assessment library

# Systems thinking
python3 -m systems.causal_loops --list
python3 -m systems.leverage --rank --location-id UUID
python3 -m systems.stock_flow --run --model soil_carbon --location-id UUID --duration 365

# Trends and geostatistics
python3 -m services.trends.estimator --metric-key soil_carbon_delta --location-id UUID
python3 -m services.trends.forecasting --metric-key crop_revenue --location-id UUID --horizon 30
python3 -m services.geostatistics.cli variogram --location-id UUID --property soil_carbon

# Threatcasting
python3 -m services.threatcasting create-threat --location-id UUID --name "Drought" --type climate --severity high
python3 -m services.threatcasting briefing --location-id UUID

# Stakeholder ecosystem
python3 -m services.analytics.cli_stakeholders landscape
python3 -m services.analytics.cli_stakeholder_trust profile PARTY_UUID

# Strategy and governance circles
python3 -m services.analytics.cli_strategy_map dashboard
python3 -m services.analytics.cli_governance_roles list --location-id UUID

# Management and planning
python3 -m services.management work-item list --org-id UUID
python3 -m services.planning budget list --org-id UUID
python3 -m services.capital.cli capacity --location-id UUID

# Governance framework (Baal on Gnosis)
python3 -m services.governance.cli framework list
python3 -m services.governance.cli baal proposals

# Tactical and simulation reports
python3 -m services.export.report_generator --type tactical_layer --location-id UUID
python3 -m services.export.report_generator --type simulation_wargame --location-id UUID

# Migration
python3 -m services.migration status
python3 -m services.migration migrate
```

See [AGENTS.md](AGENTS.md) for the full command catalogue and [CHANGELOG.md](CHANGELOG.md) for release history.

---

## CI And Contributing

CI runs on OneDev via `.onedev-buildspec.yml` as a single `ci` job on every push and pull request (~14 minutes). The pipeline is structured for fast feedback:

1. **Supply-chain gates**: Secret scanning (`check-tracked-secrets.sh`) and image digest pinning (`check-image-digests.sh`).
2. **Fast-fail steps** (fail immediately, no Docker needed):
   - `ruff` security scan (`S`, `BLE` selectors)
   - `pip-audit` dependency vulnerability check
   - `ci-check.sh` — Python import validation, CLI smoke tests, TypeScript build
   - Unified CLI smoke test (`python3 -m services.cli --help`)
3. **Infrastructure**: Docker Compose brings up PostgreSQL 16, ClickHouse 25.8, Redis 7, cache, and Directus. Database is seeded and metrics are computed.
4. **Version verification**: Reads `VERSION` file and compares to `services.__version__` and `KOKONUT_GIT_SHA` in running containers.
5. **Full test suite**: 4,034+ Python tests, 62 Solidity tests, 52 Directus hook tests via `verify-full-test-suite.sh` (fails closed on any skip).
6. **Static analysis**: Slither (Solidity), Aderyn (Solidity), and Semgrep (`python.lang.security` + `python.lang.correctness`).
7. **Solidity**: `forge fmt --check`, `forge build --sizes`, `forge test`.
8. **Directus hooks**: `npm ci`, `npm run build`, `npm test`.

The runner connects to the Compose network via `docker network bridge` for database access during tests. `compute-metrics.sh` runs in CI to populate governed metric rows required by platform-integrity tests.

This repository is hosted on a self-managed Git instance (not GitHub), so GitHub-specific workflows, rulesets, and `.github/` config do not apply.

Contributing guidelines:

> [!IMPORTANT]
> - `AGENTS.md` is the canonical command reference and contributing workflow — update it when adding commands, env vars, or conventions.
> - Branch from `main` (`feat/...`, `fix/...`, `chore/...`), open a pull request, and merge through the OneDev UI or the `tod` agent skills (`work-on-issue`, `submit-pull-request-work`) once reviewed. Never push directly to `main` except for hotfixes.
> - Seed files must be idempotent with `ON CONFLICT` guards and `psql -v ON_ERROR_STOP=1`.

---

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

---

## Repository Layout

```text
config/             Docker, PostgreSQL, ClickHouse, Caddy, Directus, Mosquitto, and worker crontab config
contracts/          Foundry project with 11 Solidity contracts, deploy scripts, and upgrade tooling
dashboards/         Metabase dashboard templates with backing SQL
docs/               108 guides and references; see Documentation below
extensions/         Directus lifecycle hooks, workflow rules, metric hooks, AI helpers
migrations/         Migration tooling and legacy migration helpers
schemas/            PostgreSQL (344 migrations, up to #352) and ClickHouse schemas, Directus snapshots, seed files
scripts/            29 scripts for setup, seed, schema, metrics, backup, restore, health-check, CI, and verification
sdk/                JavaScript/TypeScript and Python SDKs
tests/              382 test files covering platform services and invariants
```

```text
Dockerfile.worker       Worker container for cron-based ingestion
Dockerfile.gateway      FastAPI gateway / Field Collector app
Dockerfile.grpc         gRPC server container
docker-compose.yml      Base services (PostgreSQL 16, ClickHouse 25.8, Redis 7, Directus 12.1.1, Metabase 0.62.4, Caddy, Mosquitto 2)
docker-compose.prod.yml     Production overlay (resource limits, no direct port exposure)
docker-compose.traefik.yml  Traefik overlay (disables Caddy, adds Traefik labels)
docker-compose.worker.yml   Worker overlay (cron-based Python ingestion container)
```

The `services/` directory contains 65+ Python service modules organized by domain:

```text
services/
  Core:             common, core, cli.py, migration, gateway, scheduler, events, security
  Data:             ingestion, metrics, stream, data_stream, data_module, cache, storage
  Analytics:        analytics, crisp, scoring, forecast, fortune500, revenue_multiplier,
                    finance, trends, geostatistics, systems, simulation, innovation
  Governance:       governance, decision, orientation, feedback, delphi, threatcasting,
                    graph_projection, workflow_specs
  Organization:     management, planning, capital, guilds, federation
  Web3:             attestation, credit_class, iri, rdf, registry, certificates, abundance, flows
  Intelligence:     agents, predictions, strategy_markup, schema_introspection
  External:         grpc, drivers, export, sandbox, metadata_api, linkml, csw, geostory,
                    maps, thesaurus, office
```

See `AGENTS.md` for the full service catalogue with CLI commands, or `python3 -m services.cli --help` for the unified meta-CLI.

---

## Security And Privacy

> [!IMPORTANT]
> - Secrets come from environment variables; do not commit `.env` or private keys. See `.env.example` for the current catalog and placeholder warnings.
> - Public EAS metadata stores hashes, CIDs, UIDs, chain labels, transaction hashes, and timestamps; private evidence remains offchain.
> - Agent-generated summaries are drafts and must use approved governed data; agents **cannot** verify or publish their own outputs.

Additional security measures:

- Base Compose keeps PostgreSQL, ClickHouse, and Redis internal, binds Directus and MQTT to loopback, and exposes Caddy plus gRPC. The production overlay removes direct application-service exposure.
- `PUBLIC_RESTRICT=true` disables unauthenticated public Directus data access.
- Directus rate limiting (100 req/s general, 5 login attempts per 15-min lockout) and login throttling are enabled.
- Public stakeholder feedback requires explicit consent and public-summary scoping; raw stakeholder feedback remains private by default.
- Public carbon claims require Evidence Maturity Level 6 with external verification and methodology reference.
- ClickHouse HTTP insert paths validate interpolated values before SQL construction.
- KGP upgrades require a 48-hour timelock delay and human approval.
- All container images are pinned to `@sha256` digests; CI fails on unpinned images.

See [Deployment](docs/deployment.md), [Attestation Guide](docs/attestation-guide.md), [Agent Access](docs/agent-access.md), and [KGP Security Model](docs/kgp-security-model.md) for operational security details.

---

## Documentation

Documentation lives under `docs/`. Key entry points:

| Document | Description |
|----------|-------------|
| **Core Platform** | |
| [User Guide](docs/user-guide.md) | Role workflows, data entry, lifecycle, dashboards, analytics, export |
| [Architecture](docs/architecture.md) | System overview, data flow, security model |
| [Platform Integrity](docs/platform-integrity.md) | Cross-cutting integrity boundaries and operational guarantees |
| [Migrations](docs/migrations.md) | Ordered migration execution, checksums, drift detection, and recovery |
| [Gateway](docs/gateway.md) | Route policy, authentication, default-deny behavior, rate limits, and audit |
| [Data Dictionary](docs/data-dictionary.md) | Collections, fields, governed metrics |
| [API Reference](docs/api-reference.md) | Directus REST/GraphQL and ClickHouse access notes |
| [gRPC API](docs/grpc-api.md) | Type-safe external API, streaming, Protobuf schemas |
| **Metrics & Analytics** | |
| [Metric Verification](docs/metric-verification.md) | Draft computation, independent human verification, and public exposure |
| [Metrics by Development Phase](docs/metrics-by-phase.md) | Which metrics each phase enables, how they're measured, and collective insights |
| [Prediction Calibration](docs/prediction-calibration-and-outside-view.md) | Shared prediction ledger, outcomes, calibration gates, reference classes |
| [CRISP Risk Scoring](docs/crisp-risk-scoring.md) | Five-dimension risk scoring and AAA-D composite rating |
| [EBF Scorecard Guide](docs/ebf-scorecard.md) | EBF pillars, rubric, scorecards, trust graphs |
| **Web3 & Verification** | |
| [Attestation Guide](docs/attestation-guide.md) | EAS on Celo, schemas, onchain/offchain attestations |
| [Credit Lifecycle](docs/credit-lifecycle.md) | Issuance, custody, balances, retirement review, and certificates |
| [IRI System](docs/iri-system.md) | IRI generation, versioning, resolution, and anchoring |
| [RDF and SPARQL](docs/rdf-sparql.md) | RDF triple store, SPARQL queries, and linked data |
| [Data Stream](docs/data-stream.md) | Chronological data posts, file attachments, blockchain anchoring |
| **Governance & Strategy** | |
| [Stakeholder Ecosystem](docs/stakeholder-ecosystem.md) | Stakeholder foundation, trust, engagement, and governance |
| [Threatcasting and Backcasting](docs/threatcasting-and-backcasting.md) | Threat intelligence, future narratives, principles, and pathway planning |
| [Delphi](docs/delphi.md) | Real-time Delphi studies, consensus, facilitation, and approval boundaries |
| [Management](docs/management.md) | Work items, responsibilities, escalation, and SLA tracking |
| [Strategy Markup](docs/strategy-markup.md) | Strategy markup language for capability and initiative mapping |
| **Operations** | |
| [Deployment](docs/deployment.md) | Docker setup, environment variables, backup, operations |
| [Operator Guide](docs/operator-guide.md) | Day-2 operations, monitoring, and incident response |
| [Reviewer Guide](docs/reviewer-guide.md) | Metric verification, governed record review, and approval workflows |
| [Secrets Management](docs/secrets-management.md) | Encrypted secrets, SOPS, and environment variable handling |
| [CI Pipeline](docs/ci.md) | CI pipeline structure, fast-fail steps, and local reproduction |
| **Smart Contracts** | |
| [Gnosis Mainnet Deployment](docs/gnosis-mainnet-deployment.md) | Deployed addresses, authority matrix, verification status |
| [KGP Protocol](docs/kgp-protocol.md) | Kokonut Guild Points protocol specification |
| [KGP Deployment](docs/kgp-deployment.md) | KGP deployment runbook with staged timelock flow |
| [KGP Security Model](docs/kgp-security-model.md) | Upgrade authority, timelock, and role security |
| [Upgrades](docs/upgrades.md) | Onchain deployment and upgrade history |
| **Domain Guides** | |
| [Export Guide](docs/export-guide.md) | Report types, data exports, and report snapshots |
| [Green Paper](docs/green-paper.md) | Comprehensive publication-ready document |
| [Bio Factory Operations](docs/bio-factory-operations.md) | Bio-input production, quality testing, and recipe management |
| [Ecological Modeling](docs/ecological-modeling.md) | Ecological simulation and trophic analysis |
| [Business Process Management](docs/business-process-management.md) | Process mining, predictive BPM, and process health |
| [Evidence Lineage Graph](docs/evidence-lineage-graph.md) | Graph-based evidence tracing and validation chains |
| [Dependency Capabilities](docs/dependency-capabilities.md) | All dependency updates mapped to platform capabilities |
| [Technology Roadmap](docs/technology-roadmap.md) | Technology roadmap and implementation timeline |
| **Workflow Specifications** | |
| [Workflow Specifications](docs/workflow-specifications.md) | 30+ governed workflow specs with parity metadata |

Additional docs cover: CIDS mapping, stakeholder feedback, participatory metrics, holistic well-being, financial sustainability, risk mitigation, scaling roadmap, capital efficiency, commons liberation, GNH alignment, regenerative outcomes, open-source capitalist scaling, commons governance, EBF trust graph, spreadsheet guide, common foundations checklist, agent safety, public report disclaimer, advisor review guide, PRD completion scope, partner dashboards, sandbox, subgraph guide, EBF implementation memo, dMRV architecture, field data collection guide, telemetry infrastructure, OpenAPI spec (`docs/openapi.yaml`), Adelphi governance pilot, and 30+ per-entity workflow specifications.

---

## License

Open source. See [LICENSE](LICENSE).
