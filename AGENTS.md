# Repository Guidelines

## Project Shape

- PostgreSQL and Directus are the canonical schema/API layer.
- ClickHouse is the analytical event store.
- Python services live under `services/` and should be runnable with `python3 -m ...`.
- SQL schemas live under `schemas/postgres/`; seed data lives under `schemas/seeds/`.
- Directus hooks live under `extensions/kokonut-hooks/`.
- Solidity contracts live under `contracts/` (Foundry project).
- Foundry dependencies (`contracts/lib/`) are committed to the repo. Do not add `lib/` to `.gitignore`.
- Celo is the primary EAS attestation chain. EAS v1.3.0 is deployed on Celo mainnet.
- The KokonutResolver (`0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad`) gates attestation to allowed attesters.
- Resolver ownership is on the Kokonut multisig (`0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5`).
- Kokonut Adelphi (`kokonut-adelphi`) is the canonical pilot/demo farm. Do not reintroduce the old Kisumu demo identity as source of truth.
- Colony is the Guild execution/reputation layer. Gnosis Moloch DAO remains the treasury governance layer.
- Agent contract identity, x402/ERC-8004 payments, escrow, and reputation logic are external to `Kokonut-Agentic-Marketplace`.

## Data Lifecycle

- Use `draft`, `submitted`, `verified`, `published` for governed lifecycle state.
- `rejected` is allowed for rework/exception paths.
- Do not overload lifecycle `status` with payment, attestation, or domain state.
- Use fields like `payment_status`, `attestation_uid`, `attested_at`, and `revocation_date` for domain-specific state.

## Local Commands

- Start services: `docker compose up -d`
- Apply schemas/base seeds: `./scripts/seed.sh`
- Apply pilot data: `./scripts/seed-pilot.sh`
- Run smoke tests: `python3 -m tests.test_smoke`
- Run CLI tests: `python3 -m tests.test_cli`
- Run attestation tests: `python3 -m tests.test_attestation`
- Run Directus metadata tests: `python3 -m tests.test_directus_metadata`
- Verify MVP definition of done: `./scripts/verify-mvp.sh`
- Run CI checks: `./scripts/ci-check.sh` (also runs on push via `.github/workflows/ci.yml`)
- Build Solidity contracts: `cd contracts && forge build`
- Run Solidity tests: `cd contracts && forge test`
- Format Solidity: `cd contracts && forge fmt`
- Show EAS chain info: `python3 -m services.attestation.cli info --chain celo`
- List Kokonut schemas: `python3 -m services.attestation.cli schema list`
- Compute metrics: `python3 -m services.metrics --compute --metric value_flowed --location-id UUID`
- Compute all metrics (single location): `python3 -m services.metrics --compute --all --location-id UUID`
- Compute all metrics (all locations): `python3 -m services.metrics --compute --all-locations`
- Compute all metrics as verified (all locations): `python3 -m services.metrics --compute --all-locations --verify`
- Compute all metrics (script): `./scripts/compute-metrics.sh`
- List metrics: `python3 -m services.metrics --list`
- NDVI trends: `python3 -m services.analytics --ndvi-trends --location-id UUID`
- Water resilience: `python3 -m services.analytics --water-resilience --location-id UUID`
- Crop diversity: `python3 -m services.analytics --crop-diversity --location-id UUID`
- Intervention impact: `python3 -m services.analytics --intervention-impact --location-id UUID`
- Soil health: `python3 -m services.analytics --soil-health --location-id UUID`
- Water access: `python3 -m services.analytics --water-access --location-id UUID`
- Environmental baseline: `python3 -m services.analytics --environmental-baseline --location-id UUID`
- Carbon balance: `python3 -m services.analytics --carbon-balance --location-id UUID`
- GHG emissions: `python3 -m services.analytics --ghg-emissions --location-id UUID`
- Tree carbon: `python3 -m services.analytics --tree-carbon --location-id UUID`
- Regenerative score: `python3 -m services.analytics --regenerative-score --location-id UUID`
- Emission factors: `python3 -m services.analytics --emission-factors`
- Carbon benchmarks: `python3 -m services.analytics --carbon-benchmarks`
- CIDS export: `python3 -m services.registry.cids_export --location-id UUID`
- Ingestion status: `python3 -m services.ingestion.status log --source openweathermap`
- Ingestion indexers: `python3 -m services.ingestion.status indexers`
- Ingestion summary: `python3 -m services.ingestion.status summary`
- Gnosis Chain indexer: `python3 -m services.ingestion.gnosis_indexer`
- GIS boundary import: `python3 -m services.ingestion.gis_import --file boundaries.geojson --target location`
- Market data (live): `python3 -m services.ingestion.market_data --source world_bank`
- Market data (seed): `python3 -m services.ingestion.market_data --source seed`
- Sensor ingestion (CSV): `python3 -m services.ingestion.sensor_ingester --file data.csv`
- Sensor ingestion (single): `python3 -m services.ingestion.sensor_ingester --sensor UUID --value 25.3`
- Sensor list: `python3 -m services.ingestion.sensor_ingester --list`
- Sensor calibration: `python3 -m services.ingestion.sensor_ingester --calibration`
- Anomaly detection: `python3 -m services.ingestion.anomaly_detector`
- Anomaly detection (sensor): `python3 -m services.ingestion.anomaly_detector --sensor UUID`
- Baseline check: `python3 -m services.ingestion.anomaly_detector --baseline-check`
- Alert rules list: `python3 -m services.ingestion.anomaly_detector --list-rules`
- AI summary: `python3 -m services.agents.ai_summary --location-id UUID --type combined`
- Dataset refresh: `python3 -m services.export.dataset_refresh --all`
- Report auto-generation: `python3 -m services.export.report_generator --auto --location-id UUID`
- Climate-impact report: `python3 -m services.export.report_generator --type climate_impact --location-id UUID`
- CIDS export tests: `python3 -m tests.test_cids_export`
- Agent safety tests: `python3 -m tests.test_agent_safety`
- Agent task tests: `python3 -m tests.test_agent_tasks`
- Agent task catalogue: `python3 -m services.agents.tasks --list`
- CIDS export agent: `python3 -m services.agents.cids_agent --location-id UUID --summary`
- Feedback synthesis agent: `python3 -m services.agents.feedback_agent --location-id UUID`
- Directus hook tests: `cd extensions/kokonut-hooks && npm test`
- Directus hook build: `cd extensions/kokonut-hooks && npm run build`
- Migration status: `python3 -m services.migration status`
- Migration apply: `python3 -m services.migration migrate`
- Migration dry-run: `python3 -m services.migration dry-run`

## Development Notes

- Prefer the smallest schema/code change that fixes the issue.
- Keep seed files idempotent with `ON CONFLICT` or equivalent guards.
- Seed files must correct stale source-of-truth rows on conflict when the record is canonical metadata, not only `DO NOTHING`.
- `seed-pilot.sh` must fail on SQL errors; do not hide seed failures with `|| true`.
- Seed scripts use `psql -v ON_ERROR_STOP=1`; preserve that behavior for all PostgreSQL seed/schema calls.
- MVP setup order: `./scripts/seed.sh`, `./scripts/seed-pilot.sh`, `./scripts/compute-metrics.sh`, then `./scripts/verify-mvp.sh`.
- Use Compose service names (`database`, `clickhouse`) instead of generated container names.
- Do not print, copy, or commit secrets from `.env`.
- Never commit private keys to Git. Bots exploit leaked secrets in seconds.
- Exposed keys require rotation and history scrubbing by an operator.
- EAS private evidence stays offchain. Store only hashes, CIDs, UIDs, chain labels, tx hashes, and timestamps in public metadata.
- When adding new EAS schemas, register on Celo mainnet first, then update `schemas/seeds/014_pilot_celo_eas.sql` with the actual `schema_uid`.
- Solidity contracts use OpenZeppelin base contracts. Don't reinvent ERC/access patterns.
- Run `forge test` before deploying any contract changes.
- Run `forge fmt` before committing Solidity changes.
- ClickHouse HTTP inserts must validate all interpolated values against strict regex patterns before SQL interpolation.
- Directus hooks pass accountability via `meta.accountability`, not `payload._accountability`.
- Role cache in `roles.ts` has a 5-minute TTL; invalidate with `clearRoleCache()` in tests.
- `pendingTransitions` Map has 30-minute TTL and 1000-entry cap to prevent memory leaks.
- Use `try/finally` with `db.close()` for all PostgreSQL connection blocks in ingestion scripts.
- `verify_review.result` uses `approved`/`rejected`/`needs_info`, not `verified`.
- Field Worker create permissions exclude `status` — lifecycle starts at `draft` by default.
- MVP-critical pilot `expense_event` and `harvest_event` rows require populated `source_system`, `source_id`, and `source_raw`.
- `metric_value` table stores computed governed metric results.
- Metric computation: run `./scripts/compute-metrics.sh` after seeding to populate verified `metric_value` rows for public metric views.
- Metric governance: `metric_definition` has `validation_tests`, `report_usage`, `deprecation_policy` fields populated via `schemas/seeds/022_metric_governance.sql`.
- Public aggregate views must not expose unverified metrics; `v_public_metric_summary` reads only `metric_value.verified = TRUE`.
- Public aggregate views require a verified or published `farm_registry_record` before exposing a location.
- Public attestation summaries join `attestation_record` to `location` through `subject_type = 'location'` and `subject_id`.
- Public attestation summaries are scoped to Celo.
- CIDS v3.2.0 Essential Tier export is implemented in `services/registry/cids_export.py`; keep PostgreSQL/Directus canonical and treat CIDS as compatibility/export mapping.
- Portfolio ClickHouse views live in `schemas/clickhouse/005_portfolio_views.sql` and should use existing analytical mirrors instead of creating a separate portfolio ranking model.
- Green Paper review dashboards live in `dashboards/metabase/20_evidence_gap_dashboard.json` and `dashboards/metabase/21_stakeholder_feedback_dashboard.json` with SQL under `dashboards/metabase/sql/`.
- Report snapshots generated by `services/export/report_generator.py` attach public-interest context and populate `public_interest_summary`, `uncertainty_notes`, `negative_findings`, and `affected_community_voice` when available.
- Agent task catalogue and output schemas live in `services/agents/tasks.py`; do not add agent capabilities without documenting inputs, outputs, writes, and risk.
- CIDS export agent (`services/agents/cids_agent.py`) is read-only and wraps the canonical CIDS exporter.
- Feedback synthesis agent (`services/agents/feedback_agent.py`) must use public summaries and aggregate private/no-consent signals; never expose raw private feedback.
- Stakeholder feedback is private by default. Public feedback requires `consent_given = TRUE`, public consent scope, `status = 'published'`, and a non-empty `public_summary`.
- Public impact claims require evidence maturity >= 4; public carbon claims require evidence maturity 6, `claim_type = 'third_party_verified_claim'`, `external_verifier`, `methodology_ref`, and `published` status.
- Participatory metric proposals use `proposed`, `discussed`, `approved`, `implemented`, `deprecated`, and `rejected`, not the governed record lifecycle.
- Directus Phase 2 workflow hooks live in `extensions/kokonut-hooks/src/feedback.ts`, `metric-proposal.ts`, `impact-claim.ts`, and `agent-safety.ts`.
- Framework reference data is canonicalized by `schemas/seeds/023_impact_frameworks.sql`; Adelphi mappings and Guild/DAO alignment are in `schemas/seeds/024_adelphi_alignment.sql`.
- Impact framework rows should be nonblank and active for SDGs, 8 Forms of Capital, Pillars of Value, EBF, CRISP, and regeneration principles.
- Baseline calculators (revenue, asset_value, cash_flow, cost) query the `location` table directly.
- `revenue_multiplier_config` table stores dimension constants (DB-backed, not hardcoded).
- Forecast engine writes per-cycle outputs with `crop_cycle_id`.
- Forecast engine estimates carbon sequestration from SOM changes.
- Forecast engine prices biodiversity credits from species observation count.
- Forecast engine projects retained value from historical reinvestment rates.
- `CALCULATION_VERSION` is date-based (`vYYYY.MM`), auto-bumps monthly.
- Per-square-meter revenue: `Total Production = Planting Density/m² × Bed Area m² × Beds/Plot × Plots × (1 − Loss Rate)`. Activates when `crop_cycle.planting_density` AND `plot.bed_area_sqm` AND `plot.bed_count` are set; falls back to ha-based model otherwise.

## Logging & Retry

- Operational modules use `services.common.logging.get_logger(name)` (Python `logging`), not `print()`.
- CLI modules (`cli.py`) continue to use `print()` for user-facing output.
- `KOKONUT_LOG_LEVEL` env var controls log level (default: `INFO`).
- Retry config: `RETRY_MAX_RETRIES`, `RETRY_BACKOFF`, `RETRY_JITTER` in `services/ingestion/config.py`.
- Retry decorator catches only transient exceptions (network, timeout, connection errors), not `ValueError`/`KeyboardInterrupt`.
- Migration runner: `python3 -m services.migration {status|migrate|dry-run}` tracks applied SQL files in `schema_migration`.

## Security & Infrastructure

- PostgreSQL and ClickHouse ports are not exposed to the host in dev mode. Use Docker exec for direct DB access.
- Docker networks: `databases` (database, cache, clickhouse) and `apps` (directus, metabase, caddy) isolate service tiers.
- Caddy reverse proxy: TLS termination (self-signed in dev, real certs in prod), request logging, security headers.
- `CADDY_DOMAIN` env var: set to your domain for TLS; defaults to `localhost` with internal self-signed CA.
- Directus and Metabase are accessed through Caddy (`/directus/*`, `/metabase/*`) or directly via internal ports.
- Directus rate limiting: 100 req/s general, 5 login attempts per 15-min lockout.
- `PUBLIC_RESTRICT=true` disables unauthenticated data access.
- `CORS_ORIGIN` defaults to `http://localhost:8055,http://localhost:3001,https://localhost`.
- `.env.example` uses placeholder warnings (`replace-with-strong-password-min-24-chars`), not real defaults.

## Blockchain Indexing

- Gnosis Chain (chain ID 100) is home of the Kokonut Moloch DAO.
- `GNOSIS_RPC_URL` defaults to `https://rpc.gnosischain.com`.
- Kokonut Moloch DAO contracts: Treasury SAFE, Token Manager, $vKKN, Loot.
- `contracts/abis/MolochV2.json` contains 9 Moloch v2 event definitions.
- `services/ingestion/gnosis_indexer.py` uses log filtering + event decoding (not subgraph).
- `schemas/seeds/020_gnosis_chain.sql` must refresh stale `kokonut-treasury` protocol and DAO wallet metadata on conflict.
- `schemas/seeds/024_adelphi_alignment.sql` realigns legacy pilot governance rows to Gnosis/Moloch metadata.

## Guilds & Frameworks

- Colony-backed Guild records live in `colony_instance`, `kokonut_guild`, `guild_contributor`, `guild_contribution`, and `guild_reputation_snapshot`.
- Guild data in this repo stores metadata, pointers, summaries, and governed records; Colony contract execution remains external.
- Adelphi syntropic/regenerative evidence lives in `farm_zone`, `farm_practice_event`, and `farm_impact_mapping`.
- Use Knowledge Base facts as the starting source for Adelphi unless a newer governed source is explicitly provided.

## Modeled Outputs

- `metric_version` table tracks formula changes for each metric definition.
- `ai_summary` generator writes structured text summaries to `ai_summary` table.
- Agent-generated summaries must be drafts and must use approved governed data; Agent Write can create `ai_summary` but not publish it.
- Agents can draft, submit, or reject their own outputs, but cannot verify or publish them. Enforce this in DB constraints, Directus hooks, and `services/agents/safety.py`.
- Agent high-risk actions (`publish`, `attest`, `onchain_submit`, `delete`, `bulk_update`, `financial_write`, `status_change_to_published`) must be logged with human approval required.
- `dashboard_dataset` refresh executes stored SQL queries from `dashboard_dataset.sql_query`.
- `report_snapshot` `--auto` flag generates all 5 report types in one run.
