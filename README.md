# Kokonut Intelligence Platform

Open-source intelligence layer for regenerative farm operations, financial performance, ecological outcomes, partner reporting, and Web3 verification.

PostgreSQL and Directus are the canonical schema/API layer. ClickHouse stores analytical events. Python services compute metrics, forecasts, exports, registry payloads, AI summaries, and ingestion jobs. EAS on Celo anchors public verification metadata while private evidence stays offchain.

**Repo stats**: 49 tests · 14 agents · 37 report types · 42 dashboards · 49 seed files · 39 docs

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

Or using Make targets:

```bash
make seed          # applies schema + base seeds
make ci            # runs full local CI (105 checks)
make test          # runs pytest over all tests
make lint          # ruff lint check
make typecheck     # mypy type check
make fmt           # ruff format
make forge-test    # Solidity tests
make hooks-test    # Directus hooks tests
```

Run the full local check with `./scripts/ci-check.sh` or `make ci`. For sandbox-specific setup, see [Developer Sandbox](docs/sandbox.md). For deployment guidance, see [Deployment](docs/deployment.md).

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

## Core Capabilities

- **Governed farm operations**: Activities, harvests, sales, expenses, losses, labor, field notes, inventory, maintenance, revenue events, and partner-scoped access through Directus.
- **Intelligence and analytics**: Versioned metric definitions, scenario forecasts, Fortune 500-style farm scoring, ecological analytics, revenue multiplier opportunity maps, EBF scorecards with trust graphs, portfolio messy roll-ups, and AI-generated summaries.
- **Impact accountability and evidence**: Evidence maturity levels, stakeholder feedback, impact claims, participatory metric proposals, holistic well-being, financial resilience, capital efficiency, commons liberation, GNH alignment, regenerative outcomes, open-source scaling, commons governance, and CIDS Essential Tier JSON-LD export.
- **Web3 verification**: EAS schemas on Celo, KokonutResolver attester gating, onchain/offchain attestations, private evidence hashes, wallet activity, Gnosis DAO metadata, and public attestation summaries.
- **Governance and guilds**: Colony-backed Guild metadata, contribution records, reputation snapshots, anti-capture governance, flexible redistribution, federation protocols, and DAO proposal links while Gnosis Moloch remains the treasury governance layer.
- **Agent ecosystem**: 14 agent identities with capability manifests, tasks, action logs, AI summaries, and scoped MCP/Directus access. Agents can draft and submit but cannot verify, publish, attest, or score. Contract identity, payments, escrow, and marketplace logic remain external to this repo.

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
python3 -m services.metrics --compute --all-locations --verify

# Reports (37 types; use --auto for all)
python3 -m services.export.report_generator --auto --location-id UUID
python3 -m services.export.report_generator --type climate_impact --location-id UUID

# CIDS export
python3 -m services.registry.cids_export --location-id UUID

# Agents (14 agents; see AGENTS.md for full list)
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
| Python checks | Ruff lint, 105-check CI script, CLI smoke tests, attestation tests, integration tests |
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

## Repository Layout

```text
config/             Docker, PostgreSQL, ClickHouse, Caddy, and Directus config
contracts/          Foundry project for KokonutResolver and EAS-related contracts
dashboards/         42 Metabase dashboard templates with backing SQL
docs/               39 docs — see Documentation section below
extensions/         Directus lifecycle hooks, workflow rules, metric hooks, AI helpers
migrations/         Migration tooling and legacy migration helpers
schemas/            PostgreSQL schemas, ClickHouse schemas, Directus snapshots, 49 seed files
scripts/            Setup, seed, schema, metrics, backup, verification, and CI scripts
sdk/                JavaScript/TypeScript and Python SDKs
services/           Python services for ingestion, metrics, analytics, export, agents, attestation
tests/              49 test files — smoke, CLI, attestation, metrics, EBF, agents, modules
```

## Security And Privacy

- Secrets come from environment variables; do not commit `.env` or private keys. See `.env.example` for the full catalog (44 env vars with placeholder warnings).
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

All 39 docs live under `docs/`. Key entry points:

| Document | Description |
|----------|-------------|
| [User Guide](docs/user-guide.md) | Role workflows, data entry, lifecycle, dashboards, analytics, export |
| [Architecture](docs/architecture.md) | System overview, data flow, security model |
| [API Reference](docs/api-reference.md) | Directus REST/GraphQL and ClickHouse access notes |
| [Data Dictionary](docs/data-dictionary.md) | Collections, fields, governed metrics |
| [AGENTS.md](AGENTS.md) | Canonical command reference (CLI, analytics, ingestion, agents, tests) |
| [CHANGELOG.md](CHANGELOG.md) | Release history and unreleased changes |
| [Green Paper V1](docs/green-paper-v1.md) | Comprehensive 15-section publication-ready document |
| [Export Guide](docs/export-guide.md) | 37 report types, data exports, report snapshots |
| [EBF Scorecard Guide](docs/ebf-scorecard.md) | EBF pillars, rubric, scorecards, trust graphs |
| [Attestation Guide](docs/attestation-guide.md) | EAS on Celo, schemas, onchain/offchain attestations |
| [Deployment](docs/deployment.md) | Docker setup, environment variables, backup, operations |
| [Agent Access](docs/agent-access.md) | MCP, agent-scoped tokens, permissions, audit logging |
| [Agent Workflows](docs/agent-workflows.md) | Agent task catalogue, output schemas, and safety rules |
| [Evidence Maturity](docs/evidence-maturity.md) | Evidence maturity levels and public carbon claim rules |
| [Reporting Principles](docs/reporting-principles.md) | Public-interest reporting principles and report snapshot fields |

Additional docs cover: CIDS mapping, stakeholder feedback, participatory metrics, holistic well-being, financial sustainability, risk mitigation, scaling roadmap, capital efficiency, commons liberation, GNH alignment, regenerative outcomes, open-source capitalist scaling, commons governance, EBF trust graph, spreadsheet guide, common foundations checklist, agent safety, public report disclaimer, operator guide, reviewer guide, advisor review guide, PRD completion scope, partner dashboards, sandbox, subgraph guide, EBF implementation memo, and OpenAPI spec (`docs/openapi.yaml`).

## License

Open source. See [LICENSE](LICENSE).
