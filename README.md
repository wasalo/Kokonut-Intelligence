# Kokonut Intelligence Platform

Open-source intelligence layer for regenerative farm operations, financial performance, ecological outcomes, partner reporting, and Web3 verification.

PostgreSQL with PostGIS is the canonical operational store and schema. The Kokonut Gateway and Python domain services provide the native application layer. Directus, ClickHouse, Metabase, Prefect, Redis, Mosquitto, gRPC, and Caddy are optional or replaceable adapters; they are not all required to run the Kernel. Web3 remains a proof and coordination layer, while private evidence stays off-chain by default.

> [!IMPORTANT]
> The repository contains both the legacy Compose bundle and an isolated Kernel candidate. The candidate is under active parity and deployment acceptance; its successful build or health check is not a production-readiness claim. Use the [current refactor status and implementation guide](docs/refactor/current-state-and-implementation.md) for the authoritative gates, completed work, and remaining decisions. No physical Raspberry Pi acceptance is claimed.

## Table Of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Local Services](#local-services)
- [Core Capabilities](#core-capabilities)
- [On-Chain Deployments](#on-chain-deployments)
- [How Metrics Enable Answers](#how-metrics-enable-answers)
- [Data Lifecycle And Review](#data-lifecycle-and-review)
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
| Canonical core | PostgreSQL 16 + PostGIS | Governed schema, operational records, migrations, spatial data, durable worker state |
| Native application | FastAPI Gateway + Python domain services | Browser/API access, authorization boundaries, business operations, workers, and CLI |
| Browser operations | Gateway operator routes + optional OIDC provider | Human-reviewed location-scoped operations; Directus is not required for this path |
| Analytics adapter | Optional ClickHouse | Analytical event projections when selected and configured |
| Data-entry adapter | Optional Directus | Compatibility/admin API where its separate permission and tenant gates are accepted |
| Reporting adapters | Optional Metabase or native projections | Replaceable reporting interfaces; not required by the Kernel base profile |
| Scheduling | Native durable scheduler/workers; optional Prefect adapter | Durable runs and dispatch; provider orchestration remains configurable |
| Edge ingestion | Optional Mosquitto/MQTT and HTTP sensor receiver | Selectable edge input services; not in the minimal profile |
| Ingress | Optional Caddy | TLS and reverse proxy; the candidate app is loopback-bound by default |
| Verification | EAS on Celo + off-chain evidence storage | Public proofs and metadata; private evidence remains off-chain by default |
| Smart contracts | Foundry + Solidity | Reviewed Web3 components; repository artifacts do not prove current chain state |

See [Architecture](docs/architecture.md) for system design, data flow, and security model details.

---

## Quick Start

The default `docker-compose.yml` is the legacy integration stack. For an
isolated Kernel evaluation, first review the profile planner output. It only
prints commands; it does not start services, read secrets, migrate, seed, or
switch deployments.

```bash
# Load encrypted local settings, or prepare the documented local secret source.
source scripts/load-secrets.sh

# Review the minimal candidate Compose configuration and proposed start command.
python3 scripts/kernel-profile.py minimal --project kokonut-kernel-dev --action config
python3 scripts/kernel-profile.py minimal --project kokonut-kernel-dev --action up
```

Review the printed commands before executing them. The candidate is isolated
from legacy Compose projects and has no automatic migration or seeding. Apply
the checksummed schema migrations only after explicitly selecting the candidate
Compose project and file; see [candidate setup](docs/refactor/kernel-candidate.md)
and [migration targeting](docs/migrations.md#kernel-candidate-targeting). The
default candidate API binds to `127.0.0.1:8098` and its PostgreSQL port remains
private. Do not reuse legacy volumes or live farm data during local evaluation.

> [!TIP]
> `make ci` runs the fast-fail import/CLI/extension-build checks. It does not
> start the Kernel candidate, apply candidate migrations, or run the full test
> suite. Use the specific checks described in [CI Gates](docs/ci.md).

Or using Make targets:

```bash
make seed          # legacy Compose bootstrap; review scope before running
make ci            # fast-fail imports, CLIs, and Directus extension build
make test          # runs the Python pytest tree
make lint          # ruff lint check
make typecheck     # mypy type check
make fmt           # ruff format
make forge-test    # Solidity tests
make hooks-test    # Directus hooks tests
```

Run the fast-fail checks with `./scripts/ci-check.sh` or `make ci`. For the
strict database-backed host selection, see `./scripts/verify-local-test-suite.sh`.
For the legacy sample-data sandbox, see [Developer Sandbox](docs/sandbox.md).
For current deployment profiles and rollout limits, see
[Deployment](docs/deployment.md) and the [refactor status guide](docs/refactor/current-state-and-implementation.md).

---

## Local Services

The Kernel candidate and legacy Compose bundle are separate deployment targets.
The candidate profile planner is the entry point for Kernel work. Optional
services appear only when their overlay is selected. The table below describes
the candidate defaults; it is not a production acceptance matrix.

| Service | Base URL | Notes |
|---------|----------|-------|
| Kernel app (minimal) | `http://127.0.0.1:8098` | FastAPI app plus enabled workers in the isolated candidate project |
| PostgreSQL/PostGIS | Docker service `database:5432` | Private canonical store; no host port in the candidate base manifest |
| API and worker (standard) | API uses candidate port; worker has no HTTP port | Separate runtime roles; inspect durable run/delivery state for worker progress |
| Caddy (optional proxy overlay) | `https://127.0.0.1:8448` | Loopback default; public bind requires explicit configuration and review |
| Directus (optional adapter) | `http://127.0.0.1:18055` | Compatibility/admin integration; not the canonical Kernel API |
| ClickHouse (optional analytics overlay) | Docker service `clickhouse:8123` | Private analytics adapter |
| Mosquitto (optional MQTT overlay) | Loopback `mqtts://127.0.0.1:8883` | TLS sensor broker; requires certificates and identity provisioning |
| gRPC (optional overlay) | Private Compose service | External API transport; opt in explicitly |
| Metabase | Legacy `metabase` Compose profile | Not part of the candidate planner's standard defaults |

For the candidate planner, use an explicit project name and inspect `config`
before `up`. Do not use the legacy default project name for candidate data.

### Field Collector on the LAN

The candidate proxy is an optional overlay and binds to loopback by default.
The Kernel profile planner does not certify LAN or public exposure. Configure a
trusted certificate, bind, domain, CORS origins, and trusted-proxy policy and
complete browser acceptance before using it for phones. The older LAN recipe
below in [Deployment](docs/deployment.md) is for the legacy Compose bundle.

---

## Core Capabilities

The table below is a repository-level capability inventory, not a statement
that every workflow has full Kernel parity, an enabled provider, current live
data, or production acceptance. Review the [current refactor status](docs/refactor/current-state-and-implementation.md)
before relying on a particular capability. Optional services and external
integrations must be selected and configured explicitly.

| Category | Capability | Key Components |
|----------|------------|----------------|
| **Farm Operations** | Governed farm operations | Activities, harvests, sales, expenses, losses, labor, field notes, inventory, maintenance, revenue events; native Gateway scope is primary and Directus is optional |
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
| **Web3 & Verification** | EAS on Celo | Repository support for resolver-gated onchain/offchain attestations, private evidence hashes, and public attestation summaries; verify live schemas and resolver state before use |
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
| | dMRV architecture | Provider adapters and code paths for satellite data, IoT transports, anomaly analysis, and governed EAS verification; provider activation and hardware acceptance are deployment-specific |
| | Digital soil mapping | XGBoost-based SOC prediction with spectral indices, time-series features, geographic cross-validation |
| **Smart Contracts** | Guild protocol | Repository contracts and deployment records for Registry, Domain, TaskBoard, EvidenceReview, Governance, Points, and UpgradeTimelock |
| | Credit Token | ERC-20 implementation and proxy deployment records |
| | Price Oracle | Oracle contracts and deployment records |
| | Selective Disclosure | Privacy-preserving attestation contract implementation and deployment records |
| | KokonutResolver | EAS attester gating for registered schemas on Celo |
| **Platform** | Platform integrity | Ordered checksummed PostgreSQL migrations reject drift; API gateway defaults unknown routes to authenticated access; durable scheduler leases and event outbox/dead-letter handling |
| | Strategic reserve | Monitorable reserve registry (carbon buffer, commons reserve, financial ring-fence, capability standby, seed vault) with adequacy, drawdown headroom, trigger/breach status; release proposals are DRAFT-only and human-approved |
| | Capital accounting | Dynamic 8 Forms of Capital inventory, Keynes-inspired deferred-credit ledger, capacity assessment, consumption-vs-reinvestment diversion, value-capture risk diagnostics |
| | Tactical layer & simulation | Chess-inspired governance tactics (fork, pin, zwischenzug, double-check, promotion ladder), Monte Carlo perturbation, CRT-style clash resolution |
| | Data governance | Consent management, access logging, data portability, configurable retention/hold policy, and sharing agreements with audit trails; policy configuration and jurisdictional acceptance remain deployment work |
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
| **External** | gRPC API | Optional type-safe transport with Protobuf schemas and API-key policy; it is not required by the native Kernel profile |
| | Business Model Canvas | 1-click BMC derivation from canonical tables; 14-section comprehensive status with an exact-location Gateway read and network-wide CLI rollup |
| | State of Kokonut | Ecosystem report across locations with ecosystem-actor funding view; Mermaid + JSON visual timelines (ecosystem tree, Ikigai, farm phases, crop timelines) |

> [!NOTE]
> Agents can draft and submit governed records but **cannot** verify, publish, attest, or score. Contract identity, payments, escrow, and marketplace logic remain external to this repository.

---

## On-Chain Deployments

### Gnosis Mainnet (Chain ID 100)

Addresses below are recorded in repository deployment artifacts under
`contracts/broadcast/`. Verify current deployed bytecode, chain, resolver
ownership, and authority before interacting with them; a checked-in record does
not prove current chain state.

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
> The repository documents a 48-hour KGP upgrade-timelock design. Confirm the
> live contract configuration and role state on-chain before relying on this
> delay or authority boundary.

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

These are source-controlled schema UID records. Confirm live Celo registry
state and resolver behavior before making an attestation or external claim.

See [Attestation Guide](docs/attestation-guide.md) for schema details and registration flow.

---

## How Metrics Enable Answers

The examples below are illustrative questions and answer formats, not current
farm results or populated production measurements.

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

## Data Lifecycle And Review

Governed records use the canonical lifecycle:

```text
draft -> submitted -> verified -> published
```

`rejected` is available for rework and exception paths. Payment, attestation, execution, and domain-specific states live in dedicated fields such as `payment_status`, `attestation_uid`, `attested_at`, `execution_status`, and `revocation_date`.

Authorization is specific to the route, capability, operator grant, service
identity, and deployment. The optional Directus roles and its hooks are a
separate compatibility surface; do not assume they define native Gateway
permissions or that every collection has passed parity. Use the documented
human-review workflow for the record type. Agents may prepare or submit only
where the task contract permits; verification and publication remain explicit
human decisions.

Stakeholder feedback is private by default and requires explicit public consent
plus a non-empty public-safe summary before publication. Public carbon claims
require the applicable evidence-maturity, external-verifier, and methodology
gates.

Workflow time-based enforcement:
- Stakeholder feedback requires a minimum 7-day review period before verification.
- Metric proposals require a minimum 30-day discussion period before approval.

See [User Guide](docs/user-guide.md) for role workflows and data-entry walkthroughs.

---

## Key Commands

> [!NOTE]
> `AGENTS.md` is the canonical command reference for all local commands — CLI flags, analytics, ingestion, agents, report types, and tests. The examples below are the most common entry points.

The examples assume a correctly configured local database and the required
provider or worker identity. A command being present in the repository does
not prove that its provider is enabled or that its authorization boundary is
accepted for a deployment.

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
# Non-admin Gateway API keys/capabilities need the global `governance:read` scope.
# See services/gateway/README.md for the protected HTTP routes.

# Tactical and simulation reports
python3 -m services.export.report_generator --type tactical_layer --location-id UUID
python3 -m services.export.report_generator --type simulation_wargame --location-id UUID

# Validate migration source without a database
python3 -m services.migration validate --schemas-only

# For database status/plan/apply, select the intended Compose project and files.
# See docs/migrations.md; do not use the ambient legacy Compose default for Kernel.
```

See [AGENTS.md](AGENTS.md) for the full command catalogue and [CHANGELOG.md](CHANGELOG.md) for release history.

---

## CI And Contributing

The GitHub Actions CI workflow runs on pull requests and pushes targeting
`develop` and `main`. Feature work is reviewed into `develop`; release batches
are promoted to `main` by a separate reviewed PR. CI and Security jobs are
defined in `.github/workflows/`; their current steps and required checks are
documented in [GitHub Actions](docs/github-actions.md) and [CI Gates](docs/ci.md).
The CI runner uses a pinned Compose project and loopback high ports for
database-backed checks. A green CI run is a code gate, not a production
deployment or migration approval.

The staging workflow is manually dispatched but currently hard-disabled. The
production workflow is manual and protected by the GitHub `production`
environment; neither workflow proves that the target host is reachable or that
Kernel release gates have passed. See [Deployment](docs/deployment.md).

Contributing guidelines:

> [!IMPORTANT]
> - `AGENTS.md` is the canonical command reference and contributing workflow — update it when adding commands, env vars, or conventions.
> - Branch from `develop` (`feat/...`, `fix/...`, `chore/...`) and open a pull request to `develop` using squash or rebase; promote release batches to `main` with a separate reviewed pull request, using a merge commit when preserving release ancestry is desired. Never push directly to either protected branch.
> - Seed files must be idempotent with `ON CONFLICT` guards and `psql -v ON_ERROR_STOP=1`.

---

## Deployment

The Kernel candidate is the active refactor path; it is not yet a certified
production release. Use the profile planner, explicit Compose project, and
separate migration selection described in [Deployment](docs/deployment.md) and
[Migrations](docs/migrations.md). Legacy production Compose examples remain
reference material only. Do not start public ingress or migrate live data from
this README.

---

## Repository Layout

```text
config/             Legacy and Kernel Docker, PostgreSQL, optional provider, and worker configuration
contracts/          Foundry project, deployment records, and upgrade tooling
dashboards/         Optional/legacy dashboard templates and backing SQL
docs/               Architecture, operations, domain, and refactor documentation
extensions/         Directus lifecycle hooks, workflow rules, metric hooks, AI helpers
migrations/         Migration tooling and legacy migration helpers
schemas/            Numbered PostgreSQL migrations, optional ClickHouse schemas, Directus snapshots, and seed files
scripts/            Setup, migration, backup/restore, operations, CI, and verification scripts
sdk/                JavaScript/TypeScript and Python SDKs
tests/              Python, JavaScript/TypeScript, and Solidity tests
```

```text
Dockerfile.kernel           Kernel API/worker image with optional package targets
docker-compose.kernel-*.yml Isolated Kernel candidate and optional service overlays
Dockerfile.gateway          Legacy Compose Gateway image
Dockerfile.worker           Legacy cron worker image
Dockerfile.grpc              Optional/legacy gRPC server image
docker-compose.yml           Legacy integration stack; not the Kernel profile
```

The `services/` directory contains Python services organized by domain:

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
> - Secrets come from protected environment variables or the SOPS loader; do not commit `.env` or private keys. See `.env.example` for current variable names and safe defaults.
> - Public EAS metadata stores hashes, CIDs, UIDs, chain labels, transaction hashes, and timestamps; private evidence remains offchain.
> - Agent-generated summaries are drafts and must use approved governed data; agents **cannot** verify or publish their own outputs.

Additional security measures:

- Kernel base Compose keeps PostgreSQL private and binds the app to loopback. Optional ingress and adapters require explicit overlays; the legacy Compose network has separate bindings.
- Public routes are explicitly listed; unknown Gateway routes remain protected. Browser operator routes use optional OIDC sessions, CSRF, and explicit grants.
- Directus permissions and rate limiting apply only when its optional compatibility service is selected; they do not define native Gateway policy.
- Public stakeholder feedback requires explicit consent and public-summary scoping; raw stakeholder feedback remains private by default.
- Public carbon claims require Evidence Maturity Level 6 with external verification and methodology reference.
- ClickHouse HTTP insert paths validate interpolated values before SQL construction.
- The repository documents a 48-hour KGP upgrade-timelock design; verify live chain state before relying on the configured delay.
- Compose images are digest-pinned where required by repository checks; inspect the specific manifest selected for an environment.

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
| [Current refactor status](docs/refactor/current-state-and-implementation.md) | Consolidated architecture, implementation progress, and open gates |
| [Migrations](docs/migrations.md) | Ordered migration execution, checksums, drift detection, and recovery |
| [Gateway](docs/gateway.md) | Route policy, authentication, default-deny behavior, rate limits, and audit |
| [Data Dictionary](docs/data-dictionary.md) | Collections, fields, governed metrics |
| [API Reference](docs/api-reference.md) | Native Gateway routes plus optional Directus, gRPC, and analytics interfaces |
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
