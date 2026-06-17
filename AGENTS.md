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
- Run CI checks: `./scripts/ci-check.sh` (also runs on push via `.github/workflows/ci.yml`)
- Build Solidity contracts: `cd contracts && forge build`
- Run Solidity tests: `cd contracts && forge test`
- Format Solidity: `cd contracts && forge fmt`
- Show EAS chain info: `python3 -m services.attestation.cli info --chain celo`
- List Kokonut schemas: `python3 -m services.attestation.cli schema list`
- Compute metrics: `python3 -m services.metrics --compute --metric value_flowed --location-id UUID`
- Compute all metrics (single location): `python3 -m services.metrics --compute --all --location-id UUID`
- Compute all metrics (all locations): `python3 -m services.metrics --compute --all-locations`
- Compute all metrics (script): `./scripts/compute-metrics.sh`
- List metrics: `python3 -m services.metrics --list`
- NDVI trends: `python3 -m services.analytics --ndvi-trends --location-id UUID`
- Water resilience: `python3 -m services.analytics --water-resilience --location-id UUID`
- Crop diversity: `python3 -m services.analytics --crop-diversity --location-id UUID`
- Intervention impact: `python3 -m services.analytics --intervention-impact --location-id UUID`
- Soil health: `python3 -m services.analytics --soil-health --location-id UUID`
- Water access: `python3 -m services.analytics --water-access --location-id UUID`
- Environmental baseline: `python3 -m services.analytics --environmental-baseline --location-id UUID`
- Ingestion status: `python3 -m services.ingestion.status log --source openweathermap`
- Ingestion indexers: `python3 -m services.ingestion.status indexers`
- Ingestion summary: `python3 -m services.ingestion.status summary`

## Development Notes

- Prefer the smallest schema/code change that fixes the issue.
- Keep seed files idempotent with `ON CONFLICT` or equivalent guards.
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
- `metric_value` table stores computed governed metric results.
- Metric computation: run `./scripts/compute-metrics.sh` after seeding to populate `metric_value`.
- `revenue_multiplier_config` table stores dimension constants (DB-backed, not hardcoded).
- Forecast engine writes per-cycle outputs with `crop_cycle_id`.
- Forecast engine estimates carbon sequestration from SOM changes.
- Forecast engine prices biodiversity credits from species observation count.
- Forecast engine projects retained value from historical reinvestment rates.
- `CALCULATION_VERSION` is date-based (`vYYYY.MM`), auto-bumps monthly.
- Per-square-meter revenue: `Total Production = Planting Density/m² × Bed Area m² × Beds/Plot × Plots × (1 − Loss Rate)`. Activates when `crop_cycle.planting_density` AND `plot.bed_area_sqm` AND `plot.bed_count` are set; falls back to ha-based model otherwise.
