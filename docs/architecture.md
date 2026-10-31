# Architecture

> **Historical diagram:** [architecture-visual.html](architecture-visual.html) preserves an older full-stack deployment snapshot. Its service list, APIs, migration counts, and container topology are not current. Use this document and the [current refactor status guide](refactor/current-state-and-implementation.md) for today's Kernel architecture.

## System Overview

Kokonut Intelligence is a governed, open-source data operating system for
regenerative farm operations, financial performance, ecological outcomes, and
Web3 verification. Its deployment direction is a small native Kernel around
PostgreSQL/PostGIS, the FastAPI Gateway, and Python domain services. The older
`docker-compose.yml` bundle remains a compatibility/development stack; it is
not the Kernel profile or the default recommendation for a new deployment.

The candidate manifests are isolated from legacy Compose and intentionally do
not migrate, seed, or reuse existing data automatically. Current candidate
builds, profiles, acceptance gates, and unresolved parity work are tracked in
the [current refactor status and implementation guide](refactor/current-state-and-implementation.md).
No candidate health check is evidence of production readiness or physical
Raspberry Pi acceptance.

## Core Principles

1. **The schema is the product** — Dashboards, spreadsheets, agents, and blockchain views are interfaces. The durable asset is the canonical schema, metric dictionary, verification logic, and API contract.

2. **Web3 is a proof layer, not source of truth** — Canonical operational and financial data lives in PostgreSQL. Blockchain provides proofs, coordination, and public verifiability.

3. **Humans and AI agents use the same governed objects** — Different interfaces over the same canonical objects, permissions, and audit trails.

4. **Private evidence stays off-chain by default** — Public surfaces store hashes, CIDs, attestation UIDs, chain labels, and transaction hashes. Raw private MRV payloads remain in controlled off-chain storage.

---

## Technology Stack

| Component | Kernel role | Profile status |
|-----------|-------------|----------------|
| PostgreSQL 16 + PostGIS | Canonical schema, operational records, spatial data, and durable state | Required; private Compose service |
| Kokonut Gateway (FastAPI) | Native HTTP/API and browser operator boundary | Required; candidate app binds to loopback by default |
| Python domain services | Domain logic, CLI operations, and supervised workers | Required; worker topology varies by profile |
| Directus | Compatibility/admin data-entry adapter | Optional; separate runtime permissions and parity gate apply |
| ClickHouse | Analytical event/projection store | Optional; analytics overlay |
| Metabase | BI presentation adapter | Not part of Kernel base profiles; available in legacy Compose |
| Redis | Replaceable cache/coordination adapter | Not required by Kernel base profiles |
| Prefect | Optional workflow/orchestration integration | Disabled by default in Kernel manifests |
| Mosquitto | MQTT transport for edge sensors | Optional; requires TLS certificates and client provisioning |
| gRPC | Alternate service API transport | Optional overlay |
| Caddy | Reverse proxy and TLS ingress | Optional overlay; loopback bind by default |
| EAS / Solidity | Proof and coordination layer | Optional to local core operation; repository artifacts do not prove current external deployment state |

Python and package versions are pinned in the dependency manifests and image
build inputs. Avoid inferring runtime capabilities from upstream version
marketing notes; the repository lock files and CI define the tested set.

### Kernel Deployment Profiles

`scripts/kernel-profile.py` accepts `core`, `minimal`, `edge`, `standard`,
`analytics`, and `scale`. It prints a shell-quoted Compose command; it does not
execute Docker, load secrets, apply migrations, seed data, or switch a running
deployment.

| Profile | Shape | Important boundary |
|---------|-------|--------------------|
| `core` | Small dependency build target; optional capability packages can be added explicitly | Package/profile contract; not a certified deployment |
| `minimal` | PostgreSQL/PostGIS plus one app/API process with enabled workers | Isolated candidate profile, still under capability-parity/recovery acceptance |
| `edge` | Minimal plus selected edge media/transport resources | Requires storage, device, outage, and retention acceptance |
| `standard` | PostgreSQL/PostGIS, separate API and worker roles | Requires role provisioning, migration, worker progress, recovery, and release gates |
| `analytics` | Minimal plus private ClickHouse | Requires schema and projection parity |
| `scale` | Rejected by the planner | Multi-host, failover, concurrency, recovery, and measured sizing are not accepted |

See [profile selection and planner behavior](refactor/profile-selection.md)
and the current [refactor status](refactor/current-state-and-implementation.md)
before using a profile. ARM64/QEMU checks demonstrate software compatibility
only. No physical Raspberry Pi has been used to measure memory, storage,
thermal, or sustained-workload behavior.

The source refactor plan includes Caddy in Standard, but the current planner
adds Caddy only when `--proxy` is selected. The current `standard` profile
therefore has no TLS/public ingress by itself; this plan/code difference is an
open deployment gate.

### Container Images

Container image digests and CI checks are maintained in the Compose manifests
and repository scripts. Legacy images do not imply that those products are
required by the Kernel.

| Dockerfile | Purpose |
|------------|---------|
| `Dockerfile.kernel` | Kernel API/worker runtime image and optional package targets |
| `Dockerfile.gateway` | Legacy Compose FastAPI gateway image |
| `Dockerfile.worker` | Legacy cron-based worker image |
| `Dockerfile.grpc` | Optional/legacy gRPC runtime image |

---

## Data Lifecycle

Governed records generally follow four states. Domain-specific workflows, such as market-order fulfillment and metric verification, use their own documented state vocabulary or mapping.

```text
Draft → Submitted → Verified → Published
  │        │           │          │
  │        │           │          └─ Available to dashboards, APIs, attestations
  │        │           └─ Reviewed, validated, linked to evidence
  │        └─ Mapped to Kokonut canonical schema and submitted for review
  └─ Record created; source payload preserved where available
```

## Schema Management

Schemas are version-controlled as ordered, checksummed SQL files in
`schemas/postgres/`; seed units are separately tracked in `schemas/seeds/`.
Use `python3 -m services.migration status` to inspect the current migration
ledger instead of relying on a hard-coded count in documentation. Directus
metadata snapshots describe that optional adapter and do not supersede
PostgreSQL migrations as the schema source of truth.

- `schemas/postgres/` — Source of truth for database schema
- `schemas/directus/` — Directus snapshot exports
- `schemas/clickhouse/` — Analytical event schemas
- `schemas/seeds/` — Seed data for EAS schemas, metric definitions, governance config

---

## API Layers

| Layer | Protocol | Auth | Use Case |
|-------|----------|------|----------|
| Kokonut Gateway REST | HTTP | Public only on explicit public-route policy; otherwise API key/capability token or separate device/session flow | Native Gateway routes and mobile collection under `/api`; protected browser operator routes under `/operator/api` when optional OIDC is enabled |
| Operator browser auth | OIDC callback plus database-backed opaque session | Secure operator session cookie; CSRF token for mutations; explicit org/location grants | Human operations and review console |
| Directus REST/GraphQL | HTTP / GraphQL | Directus roles and tokens | Optional compatibility/admin adapter; not required by native Gateway |
| ClickHouse HTTP | HTTP | ClickHouse credentials | Optional analytics adapter |
| gRPC | gRPC + Protobuf | API key and route policy | Optional transport; see [gRPC API](grpc-api.md) |
| Helper CLIs | Python modules | Local process/worker-specific credentials | Migration, ingestion, analysis, and operational commands |

The route policy in `services/gateway/router.py` is public only by explicit
method/path entries; unknown routes remain protected. Mobile sync has its own
opaque device-token boundary. Browser operator routes use an optional OIDC
identity provider, database-backed session, CSRF protection, and explicit
location-scoped grants. These route classes have separate contracts: do not
infer universal endpoint or tenant parity from the presence of a Gateway.
Directus, ClickHouse, gRPC, and Caddy are not required for the minimal Kernel.

---

## Security Model

- **Identity boundaries:** Native Gateway API keys/capabilities, mobile device credentials, Delphi participant credentials, and optional OIDC operator sessions are distinct identities.
- **Governance roles:** stakeholder-steward, circle-steward, evidence-custodian, consent-custodian, grievance-owner, ecological-proxy-steward, market-relationship-owner, governance-facilitator, governance-recorder (defined in `governance_circle` / `governance_role` tables)
- **Directus policies:** Per-collection, per-action, per-field permissions apply only when the optional Directus adapter is deployed and its runtime permissions have passed parity review.
- **Tenant enforcement:** Location grants and signed PostgreSQL contexts are in place for selected access paths. Runtime-wide table grants, downstream consumers, Directus, and full RLS acceptance remain tracked separately; do not claim universal row isolation from route presence alone.
- **Audit:** The Gateway records requests to the audit store and uses a bounded local SQLite journal for replay when PostgreSQL writes fail. Audit coverage and capture state are observable, but the journal is not a human approval or evidence record.
- **Evidence:** Raw evidence stored off-chain; hashes/CIDs/attestation UIDs/chain labels/tx hashes on-chain
- **Agent scope:** This repository stores agent metadata and tasks only; marketplace identity, payment, escrow, and reputation logic are external to `Kokonut-Agentic-Marketplace`
- **KGP upgrade security:** 48-hour timelock (`KokonutGuildUpgradeTimelock.sol`) with self-administered `UPGRADER_ROLE`; only the timelock contract can propose and execute upgrades
- **Selective disclosure:** Merkle-based privacy-preserving attestations via `KokonutSelectiveDisclosure.sol`

---

## Data Ingestion

External data flows through Python services in `services/ingestion/`. Major categories include:

| Category | Scripts | Frequency | Target |
|----------|---------|-----------|--------|
| **Weather** | `weather.py`, `weather_forecast.py` | On demand | `weather_observation`, `weather_forecast`; optional analytics projection |
| **IoT Sensors** | `mqtt_subscriber.py`, `http_sensor_receiver.py`, `sensor_ingester.py`, `device_manager.py` | Event/input-driven | `sensor_reading`; MQTT transport and analytics projection are optional |
| **Remote Sensing** | `remote_sensing_fetcher.py`, `gee_remote_sensing.py`, `copernicus_remote_sensing.py` | Scheduled jobs | `remote_sensing_observation` |
| **Financial** | `market_data.py`, `yahoo_finance.py`, `price_attestation.py`, `oracle_aggregator.py` | On demand / daily | `price_observation`, on-chain attestation |
| **Blockchain** | `gnosis_indexer.py`, `baal_indexer.py`, `eas_indexer.py`, `rpc_indexer.py` | On demand | `wallet_activity_event`, `attestation_record`; optional analytics projection |
| **Climate** | `climate_data.py` | On demand | Climate data tables |
| **Analytics** | `anomaly_detector.py`, `ml_anomaly_detector.py`, `data_freshness.py`, `adaptive_sampler.py` | Periodic | Anomaly alerts, freshness checks |
| **GIS** | `gis_import.py`, `kml_import.py`, `shapefile_import.py`, `raster_metadata.py` | On demand | Spatial tables |

Ingestion and worker state use the canonical PostgreSQL records and durable
worker boundaries. ClickHouse projections are available only when the analytics
profile and its required configuration are selected. A service/module in the
repository is not proof that its external provider, credentials, schedule, or
deployment is active.

> [!NOTE]
> DApp session ingestion and metrics are deferred. Current Web3 ingestion remains focused on wallet activity, protocol interactions, EAS attestations, and governed value-flow records.

---

## EAS on Celo

The repository configures Celo as the primary chain for Kokonut attestations.
Chain IDs, resolver addresses, and schema UIDs are source-controlled
configuration; verify the live chain, contract code, resolver ownership, and
schema registration before any production attestation. Configuration alone is
not evidence that a deployment is currently active.

**Configured Contract Addresses (verify live state before use):**

| Contract | Address |
|----------|---------|
| EAS | `0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92` |
| SchemaRegistry | `0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34` |
| KokonutResolver | `0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad` |

**Registered Schemas (7):**

| Schema | UID | Use Case |
|--------|-----|----------|
| `kokonut-mrv` | `0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54` | MRV claims (location, crop, quantity, evidence) |
| `kokonut-impact` | `0xb99bb4b2a55218b8f4df1f0bd4c39400711809f13ef5d150d2903648c6590dfe` | Environmental impact (soil carbon, biodiversity, NDVI) |
| `kokonut-financial` | `0x75b42beb85dd852134dfaff3de41b8dc361ed0cb2bf93ce3009c8ec082de905b` | Financial summaries (NOI, revenue, costs) |
| `kokonut-harvest` | `0xb359f9756e3cb3597e4048dccae2842083359906fbae8dc8c0e9af8ac1b3ccff` | Harvest verification (quantity, quality, date) |
| `kokonut-compliance` | `0x59632edcf1d04be0c2dcfd572282bbd4dac518e7a92872ec45ade29876ef95f5` | Partner compliance and audit trails |
| `kokonut-bio-batch` | `0x9306a4cf6cc5a9c8aa6598a43bc62cfaa729f7490fe6b2e4cc0df10ec738ff29` | Bio-organic fertilizer batch production |
| `kokonut-data-post` | `0xf0de37f5c4a441aedb794d5585201c6ef150543dc53f894e1212f7e330205045` | Data stream posts for environmental project tracking |

> [!NOTE]
> The Data Post schema UID was corrected after Celo mainnet registration via seed `116_pilot_celo_data_post_uid.sql`. The original placeholder UID in `014_pilot_celo_eas.sql` is not overwritten; the correction seed runs after the base seed.

**Attester wallets:** Deployer `0x3394C45b5938127EB56603A6051dF26CFAF08C26` + Kokonut multisig `0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5`

**Resolver ownership:** Transferred to Kokonut multisig.

**Chain expansion:** New chains get testnet-first deployments. EAS chain config in `services/attestation/config.py` and `services/ingestion/config.py`. Add new chain config to expand.

See [Attestation Guide](attestation-guide.md) for schema details and registration flow.

---

## Smart Contracts

`contracts/` is a Foundry project with Solidity contracts, deploy scripts, and upgrade tooling. The repository includes Gnosis Mainnet deployment records, but this documentation does not verify current bytecode or contract state. Confirm the chain, deployment, ownership, and authority independently before interacting with any address. Contract source and deployment artifacts do not establish that every listed contract is currently deployed or active.

### Contract Inventory

| Category | Contract | Purpose |
|----------|----------|---------|
| **Guild Protocol** | `KokonutGuildRegistry` | Registry of all guilds with metadata and status |
| | `KokonutGuildDomain` | Domain management for guild organization |
| | `KokonutTaskBoard` | Task creation, assignment, and completion tracking |
| | `KokonutEvidenceReview` | Evidence submission and review workflow |
| | `KokonutGuildGovernance` | On-chain governance proposals and voting |
| | `KokonutGuildPoints` (KGP) | ERC-20 guild reputation points with role-based minting |
| | `KokonutGuildUpgradeTimelock` | 48-hour timelock for KGP implementation upgrades |
| **Credit** | `KokonutCreditToken` | ERC-20 credit token with burning, pausing, and role-based access (behind ERC1967 proxy) |
| **Oracle** | `KokonutPriceOracle` | On-chain price feeds with emergency updater role (behind ERC1967 proxy) |
| **Privacy** | `KokonutSelectiveDisclosure` | Merkle-based privacy-preserving attestation gating (behind ERC1967 proxy) |
| **EAS** | `KokonutResolver` | EAS attester gating for registered schemas on Celo |

### Gnosis Mainnet Deployment

All contracts are verified on GnosisScan. Key addresses:

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

See [Gnosis Mainnet Deployment](gnosis-mainnet-deployment.md) for full addresses, transactions, authority matrix, and verification status.

### KGP Protocol

Kokonut Guild Points (KGP) is an ERC-20 token with:
- Role-based minting via guild governance
- 48-hour timelock-gated upgrades (self-administered `UPGRADER_ROLE`)
- Off-chain ledger in `kgp_protocol_deployment`, `guild_reputation_event`, `kgp_claim`, `kgp_chain_event` tables
- Canonical balance view `v_kgp_canonical_balance`

See [KGP Protocol](kgp-protocol.md), [KGP Deployment](kgp-deployment.md), and [KGP Security Model](kgp-security-model.md).

### Build & Test

```bash
cd contracts
forge build       # compile
forge test        # 62 tests
forge fmt         # format
```

Deployment records live in `contracts/broadcast/*/100/run-latest.json`.

---

## Governance Circles & Roles

The platform implements a holacracy-inspired governance model with circles, roles, tensions, proposals, and tactical coordination. Defined in schemas 242–249.

### Key Tables

| Table | Purpose |
|-------|---------|
| `governance_circle` | Organizational circles with mandate and parent circle |
| `governance_role` | Roles within circles with authority and accountability |
| `governance_role_accountability` | Specific accountabilities assigned to roles |
| `governance_tensions` | Tensions identified by role holders requiring resolution |
| `governance_proposals` | Proposals raised through governance process |
| `governance_tactical_coordination` | Tactical coordination items and decisions |
| `governance_circle_links` | Cross-circle relationships and dependencies |
| `governance_cockpit` | Dashboard view of governance health and activity |

### CLI Commands

```bash
python3 -m services.analytics.cli_governance_roles list --location-id UUID
python3 -m services.analytics.cli_governance_proposals list --location-id UUID
python3 -m services.analytics.cli_governance_tensions list --location-id UUID
python3 -m services.analytics.cli_governance_tactical list --location-id UUID
python3 -m services.analytics.cli_governance_links list --location-id UUID
```

---

## Strategy System

A comprehensive strategy planning and execution system with 15+ modules and 15+ schema tables (256–284+). Covers strategy formulation, execution, monitoring, and adaptation.

### Key Subsystems

| Subsystem | Key Tables | Purpose |
|-----------|-----------|---------|
| Strategy planning | `strategy_plan`, `strategy_choices_assumptions` | Strategy definition with assumptions and choices |
| Investments | `strategy_investments_allocation` | Resource allocation and investment tracking |
| Coherence | `strategy_coherence` | Strategy coherence scoring and analysis |
| Execution | `strategy_execution_snapshots`, `strategy_portfolio_execution` | Execution tracking and portfolio management |
| Governance | `strategy_governance_reporting`, `strategy_integrity_gates` | Reporting and integrity controls |
| Risk | `strategy_risk_evidence`, `strategy_contingencies` | Risk evidence and contingency planning |
| Foresight | `strategy_foresight_frame` | Future scenario planning and foresight |
| Cascades | `strategy_cascades`, `strategy_executable_gates` | Strategy cascade and gate management |
| Evidence | `strategy_evidence_lineage` | Evidence lineage for strategy decisions |
| KPI | `strategy_kpi_refresh` | KPI refresh and alignment |
| Consultation | `strategy_consultation_communication` | Stakeholder consultation tracking |

### CLI Commands

```bash
python3 -m services.analytics.cli_strategy_map dashboard
python3 -m services.analytics.cli_strategy_map list
python3 -m services.analytics.cli_strategy_map create "Objective" --perspective internal_process
```

See [Strategy Markup](strategy-markup.md) for the strategy markup language specification.

---

## Coordination & Alliances

Alliance management and coordination workflows for multi-stakeholder operations. Defined in schemas 235–241.

### Key Tables

| Table | Purpose |
|-------|---------|
| `coordination_strategy` | Coordination strategy definitions and targets |
| `coordination_workflow_integration` | Integration points between coordination workflows |
| `coordination_learning_accounting` | Learning and knowledge accounting across alliances |
| `coordination_governance_cockpit` | Dashboard for coordination governance health |
| `coordination_trigger_safety` | Safety triggers and guardrails for coordination actions |
| `coordination_alliance_types` | Alliance type definitions and configurations |
| `coordination_integrity_controls` | Integrity controls for coordination processes |

---

## Competitive Landscape & Advantage

Competitive analysis, strategic positioning, and advantage assessment. Defined in schemas 268–286.

### Key Tables

| Table | Purpose |
|-------|---------|
| `competitive_landscape` | Competitive environment snapshots |
| `competitive_actor` | Competitor profiles and characteristics |
| `competitive_force_observation` | Porter's Five Forces and competitive pressure observations |
| `competitive_monitoring` | Ongoing competitive monitoring records |
| `competitive_health` | Competitive health scoring |
| `competitive_value_economics` | Value economics analysis per competitor |
| `advantage_assessments` | Strategic advantage evaluations |
| `advantage_fit_links` | Links between advantages and strategic fits |
| `advantage_outcomes_renewal` | Advantage outcome tracking and renewal assessment |

---

## Solution Lifecycle

End-to-end solution management from experiment to retirement. Defined in schemas 288–293.

### Key Tables

| Table | Purpose |
|-------|---------|
| `solution_lifecycle` | Solution lifecycle tracking (concept → retirement) |
| `solution_experiments` | Experiment design, execution, and results |
| `solution_funding` | Funding tracking per solution |
| `solution_adoption` | Adoption metrics and milestones |
| `solution_scale_learning_retirement` | Scale, learning, and retirement phases |
| `sequential_gate_integrity` | Gate integrity controls across lifecycle stages |

---

## Sequential Evidence & Decisions

Evidence-based decision engine with sequential analysis and odds calculation. Defined in schemas 294–296 and 299.

### Key Tables

| Table | Purpose |
|-------|---------|
| `sequential_evidence_ledger` | Ordered evidence accumulation for decisions |
| `sequential_decision_engine` | Decision engine with probability updates |
| `sequential_experiment_analysis` | Experiment analysis and outcome tracking |
| `sequential_decision_integrity` | Integrity controls for sequential decisions |

---

## Operating Pilot

Capacity-aware organizational planning with work selection, competencies, and coaching. Defined in schemas 250–255.

### Key Tables

| Table | Purpose |
|-------|---------|
| `work_selection_claims` | Work selection and prioritization claims |
| `operating_capacity_demand` | Capacity demand forecasting and tracking |
| `operating_competencies_learning` | Competency and learning management |
| `operating_coaching_resources` | Coaching and resource allocation |
| `capacity_aware_planning` | Capacity-aware planning and scheduling |
| `dual_scope_operating_pilot` | Dual-scope pilot for operational testing |

---

## Process Architecture

Process mapping, interfaces, targets, costing, and simulation. Defined in schemas 188 and 190–195.

### Key Tables

| Table | Purpose |
|-------|---------|
| `process_map` | Process definitions and relationships |
| `process_ownership` | Process ownership and accountability |
| `process_entity_mapping` | Mapping between processes and entities |
| `process_interfaces` | Interface definitions between processes |
| `process_targets` | Performance targets per process |
| `process_costing` | Cost allocation and tracking per process |
| `process_simulation` | What-if simulation parameters |
| `process_taxonomy_expansion` | Extended process taxonomy |
| `service_catalog` | Service catalog for process offerings |

---

## Nature & Future Generations

Ecological stewardship obligations and future generation principles. Defined in schema 224.

### Key Tables

| Table | Purpose |
|-------|---------|
| `stewardship_proxy_authority` | Proxy authority for nature stewardship decisions |
| `ecological_threshold` | Ecological thresholds and alert levels |
| `nature_stewardship_obligation` | Binding stewardship obligations |
| `future_generation_principle` | Principles for future generation impact |
| `nature_decision_impact` | Impact assessment of decisions on nature |

### Views

- `v_nature_stewardship_status` — Current stewardship obligation status
- `v_public_ecological_stewardship` — Public-facing ecological stewardship summary

---

## Platform Upgrade System

Governed upgrade tracking with rollback support and timelock-gated authority. Defined in schema 351.

### Key Tables

| Table | Purpose |
|-------|---------|
| `platform_upgrade` | Release and upgrade history with rollback tracking |

### Upgrade Authority

KGP upgrades follow a staged deployment pattern:
1. Temporary EOA deploys proxy and timelock
2. Timelock receives `UPGRADER_ROLE`
3. Temporary EOA revokes its own `UPGRADER_ROLE`
4. All subsequent upgrades require 48-hour timelock delay

See [Upgrades](upgrades.md) for onchain deployment and upgrade history.

---

## Configurable Container Architecture

This section describes a **farm/project domain model** that borrows container
metaphors. It is not Docker Compose guidance and does not describe deployment
profiles or infrastructure scaling. See [Kernel deployment profiles](#kernel-deployment-profiles)
for service topology.

### Architecture Layers

```text
┌─────────────────────────────────────────────────────────────┐
│                    STAKEHOLDERS LAYER                        │
│  Needs │ PoV │ Wants │ Goals │ WHW (What/How/Why)          │
│  needs_assessment │ stakeholder_aspiration │ objective      │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                 KOKONUT FRAMEWORK LAYER                      │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │  Farm Templates  │  │  Framework Specification        │  │
│  │  (Docker Image)  │  │  impact_framework               │  │
│  │  farm_template   │  │  regeneration_principle         │  │
│  │  default_zones   │  │  operations_protocol            │  │
│  │  default_gov     │  │  pillar_of_value                │  │
│  │  default_TE      │  │  form_of_capital                │  │
│  │  default_IF      │  │  impact_dimension               │  │
│  └─────────────────┘  └─────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │  Farm Compose    │  │  Implementation                 │  │
│  │  (docker-compose)│  │  farm_practice_event            │  │
│  │  farm_specification│ │  framework_phase               │  │
│  │  zones (JSONB)   │  │  regenerative_practice_checklist│  │
│  │  governance      │  │  ecological_interaction         │  │
│  │  token_economics │  │  energy_flow_measurement        │  │
│  │  impact_config   │  │  population_dynamics_record     │  │
│  └─────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│               OUTCOMES CONFIGURATION LAYER                   │
│                                                             │
│  Gov (Governance)    TE (Token Economics)                   │
│  community_governance_mechanism   commons_redistribution    │
│  anti_capture_governance_policy   algorithmic_redistribution│
│  farm_registry_record.governance  farm_registry_record.token│
│                                                             │
│  ID (Impact Dimensions)    IF (Impact Framework)            │
│  impact_dimension           impact_framework                │
│  form_of_capital            farm_impact_mapping             │
│  pillar_of_value            ebf_scorecard                   │
│  sdg                        regenerative_outcome_summary    │
└─────────────────────────────────────────────────────────────┘
```

### Key Tables

| Table | Docker Analog | Purpose |
|-------|--------------|---------|
| `farm_template` | Docker Image | Reusable configuration bundle with default zones, governance, token economics, impact frameworks |
| `farm_specification` | docker-compose.yml | Declarative per-farm configuration (zones, governance, TE, ID, IF as JSONB) |
| `farm_zone` | Container Component | Configurable zone types per farm (syntropic_plot, agroforestry, biofactory, poultry, etc.) |
| `needs_assessment` | N/A | Structured community needs with severity, urgency, mitigation tracking |
| `stakeholder_aspiration` | N/A | Formal wants/aspirations with priority, timeline, success criteria |
| `objective` | N/A | Hierarchical goals with auto-computed progress_pct |

### How to Design a New Project from Scratch

1. **Choose a template**: `farm_template` defines the "Docker image" — default zones, governance, token economics, impact frameworks
2. **Instantiate**: `farm_specification` is the "docker-compose.yml" — declarative JSONB config per farm
3. **Assess needs**: `needs_assessment` tracks what the community needs before/after launch
4. **Capture aspirations**: `stakeholder_aspiration` formalizes what stakeholders want
5. **Set objectives**: `objective` table tracks hierarchical goals with auto-computed progress

### Per-Farm Configurability

Each farm/container can independently configure:

| Component | Per-Farm Table | Global Reference |
|-----------|---------------|-----------------|
| Zones | `farm_zone.zone_type`, `farm_zone.strata_layer` | — |
| Governance | `farm_registry_record.governance_mechanism` | `impact_framework` |
| Token Economics | `farm_registry_record.token_allocation` | `revenue_multiplier_config` |
| Impact Dimensions | `farm_impact_mapping.dimension_key` | `impact_dimension` |
| Impact Frameworks | `farm_impact_mapping.framework_key` | `impact_framework` |
| Redistribution | `commons_redistribution_policy` | — |
| Anti-Capture | `anti_capture_governance_policy` | — |

---

## Grant Application & Network Diversity

The platform supports grant application tracking, returning applicant detection, and regional network diversity analysis.

### Key Tables

| Table | Purpose |
|-------|---------|
| `grant_application_history` | Tracks each grant application with cycle number, returning applicant flag, ecological metrics submitted, and on-chain/off-chain flow description |
| `regional_chapter` | Registry of regional chapters/networks with geographic region, country, chapter type |
| `network_membership` | Links farms to regional chapters with membership type and role |
| `farm_registry_record` (extended) | `returning_applicant`, `grant_count`, `total_grants_received` fields |

### Grant Application Template

A pre-configured `farm_template` called "Grant Application Template" is available for new farms applying to grants. It includes:
- Default zones (production, nursery, biofactory)
- Governance configuration
- Impact framework alignment
- Tags: `grant`, `application`, `template`, `regenerative`, `funder-ready`

### Network Diversity

The `v_network_diversity` view shows geographic and ecological diversity across the network:
- Farm count per chapter
- Countries represented
- Unique species observed
- Average regenerative score

### How Funders Use This

1. **Check land security**: `tenure_rights_assessment` + `property.deed_or_title_url`
2. **Verify pilot status**: `farm_registry_record.status` + `framework_phase` + `farm_practice_event`
3. **Review ecological metrics**: `objective` (target/current values) + `carbon_benchmark` + `soil_sample`
4. **Assess community engagement**: `training_session` + `partner` + `guild_contributor`
5. **Verify on-chain/off-chain flow**: `token_reward_distribution.linked_metric_key` + `reward_calibration_model`
6. **Check returning applicant**: `farm_registry_record.returning_applicant` + `grant_application_history`
7. **Review network diversity**: `v_network_diversity` + `v_public_regional_chapters`

---

## Organic Certification Readiness & Compliance

The platform supports organic certification tracking across USDA NOP, EU 2018/848, and IFOAM standards. The system covers the full lifecycle: transition planning, input compliance, buffer zone management, harvest segregation, inspection checklists, and readiness scoring.

### Certification Lifecycle

```text
┌─────────────────────────────────────────────────────────────────┐
│                    ORGANIC CERTIFICATION LIFECYCLE                │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Transition   │───▶│  Preparation │───▶│  Application │      │
│  │  Plan (2-3yr) │    │  & Readiness │    │  & Inspection│      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Prohibited   │    │  Buffer Zone │    │  Compliance  │      │
│  │  Substance    │    │  Management  │    │  Checklist   │      │
│  │  Tracking     │    │              │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Input Audit  │    │  Harvest     │    │  Readiness   │      │
│  │  Trail        │    │  Segregation │    │  Assessment  │      │
│  │               │    │              │    │  (0-100)     │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              CERTIFICATION ACHIEVED                       │   │
│  │  organic_certification_record.status = 'certified'       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Tables

| Table | Purpose |
|-------|---------|
| `organic_certification_record` | Certification lifecycle per standard (USDA NOP, EU 2018/848, IFOAM) |
| `organic_transition_plan` | 2-3 year transition tracking with readiness scoring and milestone dates |
| `prohibited_substance_record` | Prohibited substance usage with withdrawal period tracking |
| `buffer_zone` | Physical separation zones with PostGIS geometry and adequacy assessment |
| `organic_input_audit` | Full input audit trail with organic/prohibited flags and supplier certification |
| `harvest_handling_record` | Post-harvest organic compliance with segregation and traceability |
| `organic_compliance_checklist` | Inspector audit trail with structured JSONB checklist per standard |
| `organic_readiness_assessment` | Composite 0-100 readiness scoring across 8 dimensions |

### Readiness Score Dimensions

| Dimension | Weight | Source |
|-----------|--------|--------|
| Transition Progress | 15% | `organic_transition_plan.current_year / total_years_required` |
| Soil Health | 15% | `soil_sample` pH, organic matter, NPK, CEC analysis |
| Input Compliance | 15% | `organic_input_audit` organic_certified / total inputs |
| Pest Management | 10% | `pest_observation` + `biocontrol_release` effectiveness |
| Biodiversity | 10% | `species_observation` species count per hectare |
| Buffer Zones | 10% | `buffer_zone` width >= 3m and condition = adequate |
| Record Completeness | 10% | Presence of required records across all organic tables |
| Training | 10% | `training_session` organic practice topics completed |
| Harvest Segregation | 5% | `harvest_handling_record` organic_segregated / total harvests |

### Standards Supported

| Standard | Transition Period | Buffer Width | Key Requirements |
|----------|------------------|--------------|------------------|
| USDA NOP | 36 months | Site-specific | National List allowed substances, NOP Fertilizer List |
| EU 2018/848 | 24 months | >= 3m | EU low-risk and basic substances list |
| IFOAM | 24+ months | Site-specific | IFOAM-approved natural biocontrols, recycled nutrient cycles |

### How Certifiers Use This

1. **Review transition timeline**: `organic_transition_plan` with current_year and milestones
2. **Verify input compliance**: `organic_input_audit` with organic_certified and is_prohibited flags
3. **Check buffer zones**: `buffer_zone` with width_m, condition_status, and PostGIS geometry
4. **Audit harvest handling**: `harvest_handling_record` with organic_segregated and lot tracking
5. **Review prohibited substances**: `prohibited_substance_record` with clearance status
6. **Assess readiness**: `organic_readiness_assessment` with composite score and sub-dimensions
7. **Inspect checklist**: `organic_compliance_checklist` with structured pass/fail items
8. **Verify on-chain**: `attestation_record` with `attestation_type = 'organic'`

---

## True Cost Accounting & Triple Bottom Line

The platform implements True Cost Accounting (TCA) and Triple Bottom Line (TBL) reporting across 5 phases:

### Phase 1: Hidden Cost Accounting
- `hidden_cost_observation` tracks externalities (pollution, health, social, environmental) with monetary estimates
- `compute_true_cost_statement()` combines market costs + hidden costs + capital values

### Phase 2: Natural & Social Capital Valuation
- `natural_capital_valuation` assigns monetary values to carbon, biodiversity, water, soil, pollination
- `social_impact_valuation` monetizes training, governance, cultural preservation, health, community
- `worker_safety_observation` tracks workplace incidents
- `living_wage_benchmark` enables wage comparison

### Phase 3: Life Cycle Assessment
- `lca_assessment` tracks cradle-to-grave environmental impacts per product
- `compute_product_carbon_footprint()` and `compute_water_footprint()` compute per-unit impacts

### Phase 4: GRI Reporting
- `gri_indicator` maps platform metrics to GRI standards
- `materiality_assessment` maps stakeholder priorities vs business importance

### Phase 5: Systems Thinking
- `capital_flow_observation` tracks transfers between natural, human, social, produced, and financial capitals
- `compute_system_resilience()` scores cross-capital resilience

### Key Analytics

| Function | What It Computes |
|----------|-----------------|
| `compute_true_cost_statement()` | Market profit - hidden costs + natural + social capital = true profit |
| `compute_hidden_cost_summary()` | Hidden costs by category and subcategory |
| `compute_natural_capital_valuation()` | Natural capital value by type |
| `compute_social_impact_valuation()` | Social impact value by category |
| `compute_human_capital_score()` | Unified 0-100 human capital score |
| `compute_product_carbon_footprint()` | Emissions per kg of product |
| `compute_water_footprint()` | Blue/green/grey water per crop |
| `compute_lca_summary()` | Full lifecycle impact by stage |
| `compute_gri_compliance_score()` | % of GRI indicators with data |
| `compute_materiality_matrix()` | Stakeholder importance vs business importance |
| `compute_capital_flow_summary()` | Transfers between capitals |
| `compute_cross_capital_dependencies()` | How investment in one capital affects others |
| `compute_system_resilience()` | Cross-capital resilience score |

See [Metrics by Development Phase](metrics-by-phase.md) for the complete phase-to-metric mapping.

---

## Impact Value Chain

The platform implements the Impact Value Chain framework with organizational structure and operational planning:

### Organizational Structure
- `department` — Organizational units (Operations, Ecology, Finance, Community, Governance)
- `job_role` — Role definitions with department linkage
- `staff` — Extended with `job_role_id`, `department_id`, `hire_date`, `employment_status`

### Operational Planning
- `farm_task` — Planned tasks with scheduling, priorities, and assignees
- `weekly_plan` — Weekly action planning with budget tracking
- `development_phase` — Farm lifecycle phases with sequencing
- `framework_step` — Sequenced methodology steps with prerequisites

### Key Analytics

| Function | What It Computes |
|----------|-----------------|
| `compute_task_completion_rate()` | Task completion rate, on-time delivery, cost adherence |
| `compute_weekly_plan_adherence()` | Budget actual vs forecast, task completion |
| `compute_development_phase_progress()` | Current phase, % complete, time elapsed |
| `compute_framework_step_progress()` | Steps completed, prerequisites met, blocked steps |

---

## Scenario Parameters

The platform supports worst/base/best case scenario modeling with Monte Carlo simulation:

### Parameters
- 18 default parameters across 6 categories: yield, price, cost, weather, ecological, governance
- Each parameter has worst/base/best values with distribution types (normal, uniform, triangular)

### Key Analytics

| Function | What It Computes |
|----------|-----------------|
| `run_monte_carlo()` | 1000-sample simulation with P10-P90 percentile bands |
| `run_sensitivity_analysis()` | Per-parameter sensitivity with elasticity |
| `run_sensitivity_tornado()` | Ranked impact across all parameters |
