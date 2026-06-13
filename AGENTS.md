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
