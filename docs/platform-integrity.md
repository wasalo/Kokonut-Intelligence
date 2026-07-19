# Platform Integrity

This repository treats PostgreSQL and Directus as the canonical schema/API layer and ClickHouse as the analytical event store. PostgreSQL and ClickHouse are private Compose services: neither publishes a host port. Applications use the `databases` network and service names `database` and `clickhouse`; external access belongs behind Caddy, Directus, or the gateway.

## Trust Boundaries

```text
client -> Caddy/gateway -> Directus or application service -> PostgreSQL
                                                     \-----> ClickHouse
```

- Do not add host port mappings for PostgreSQL or ClickHouse.
- Production does not expose Directus or Metabase directly; temporary debug ports are explicit operator choices.
- Secrets belong in `.env.sops` or the runtime environment. Never print or commit private keys.
- Governed lifecycle is `draft -> submitted -> verified -> published`; `rejected` is a rework path. Payment, attestation, and domain state use separate fields.
- Agents may draft, submit, or reject their own outputs, but may not verify or publish them. High-risk actions require human approval and audit logging.
- Public metrics must be verified, and public aggregate views also require an eligible verified or published farm registry record.

## Operations

```bash
source scripts/load-secrets.sh
docker compose up -d
./scripts/seed.sh
./scripts/seed-pilot.sh
./scripts/compute-metrics.sh
./scripts/verify-platform.sh
./scripts/ci-check.sh
```

If a setup step fails, stop and repair the failed layer before continuing. Seed commands use `ON_ERROR_STOP=1`; do not suppress errors. Inspect service state with `docker compose ps` and use Compose service names for database-side diagnostics.

## Separation Of Duties

- Operators deploy infrastructure, apply migrations, and recover durable work.
- Services compute or draft records.
- Independent human reviewers verify metrics, retirement requests, and other governed records.
- Publishers expose only records that satisfy lifecycle and public-view eligibility rules.

See [Migrations](migrations.md), [Gateway](gateway.md), [Metric Verification](metric-verification.md), [Scheduler and Events](scheduler-and-events.md), and [Credit Lifecycle](credit-lifecycle.md).
