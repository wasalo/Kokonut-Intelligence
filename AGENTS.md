# Repository Guidelines

## Project Shape

- PostgreSQL and Directus are the canonical schema/API layer.
- ClickHouse is the analytical event store.
- Python services live under `services/` and should be runnable with `python3 -m ...`.
- SQL schemas live under `schemas/postgres/`; seed data lives under `schemas/seeds/`.
- Directus hooks live under `extensions/kokonut-hooks/`.

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
- Run CI checks: `./scripts/ci-check.sh`

## Development Notes

- Prefer the smallest schema/code change that fixes the issue.
- Keep seed files idempotent with `ON CONFLICT` or equivalent guards.
- Use Compose service names (`database`, `clickhouse`) instead of generated container names.
- Do not print, copy, or commit secrets from `.env`.
- Exposed keys require rotation and history scrubbing by an operator.
