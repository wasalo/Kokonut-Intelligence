# Platform Integrity

PostgreSQL/PostGIS is the canonical schema and data store. The native Gateway and Python services provide the Kernel application/API layer; Directus is an optional compatibility/admin adapter. ClickHouse is an optional analytical projection in Kernel profiles, while the legacy Compose stack retains its existing service configuration. In the Kernel candidate, PostgreSQL is private to Compose and applications connect through the `kernel` network and service name `database`; verify the selected profile before relying on an analytics service or external route.

## Trust Boundaries

```text
client -> Caddy -> Gateway / optional Directus adapter -> PostgreSQL
                         \-----> Python services ------> PostgreSQL
                         \-----> optional analytics -> ClickHouse
```

- Do not add host port mappings for PostgreSQL or ClickHouse.
- Expose optional adapters only through an explicitly configured, authenticated ingress. Do not assume Directus or Metabase is part of every Kernel profile.
- Secrets belong in `.env.sops` or the runtime environment. Never print or commit private keys.
- Governed lifecycle is `draft -> submitted -> verified -> published`; `rejected` is a rework path. Payment, attestation, and domain state use separate fields.
- Agents may draft, submit, or reject their own outputs, but may not verify or publish them. High-risk actions require human approval and audit logging.
- Public metrics must be verified, and public aggregate views also require an eligible verified or published farm registry record.

## Kernel Candidate Operations

The Kernel planner prints reviewed Compose commands; it does not start services,
apply migrations, seed data, or stop another project. Start with configuration
inspection and follow the named candidate migration/rollback procedure:

```bash
source scripts/load-secrets.sh
python3 scripts/kernel-profile.py minimal --project kokonut-kernel-dev --action config
python3 scripts/kernel-profile.py minimal --project kokonut-kernel-dev --action up
./scripts/compute-metrics.sh
./scripts/verify-platform.sh
./scripts/ci-check.sh
```

Candidate volumes are isolated from the legacy stack. Migrations and seeds are
separate, explicitly selected operations; do not run the legacy bootstrap or
pilot seed scripts against a Kernel candidate by default. If a setup step fails,
stop and repair that layer before continuing. Use the selected candidate project
name for Compose diagnostics and its service names for database access.

## Legacy Integration Stack Operations

The following commands operate the legacy root Compose stack and its schema
bootstrap. Use them only when intentionally working on legacy compatibility;
they do not configure or migrate the Kernel candidate:

```bash
docker compose up -d
./scripts/seed.sh
./scripts/seed-pilot.sh
```

Seed commands use `ON_ERROR_STOP=1`; do not suppress errors. Inspect legacy
service state with `docker compose ps` and use Compose service names for
database-side diagnostics.

## Separation Of Duties

- Operators deploy infrastructure, apply migrations, and recover durable work.
- Services compute or draft records.
- Independent human reviewers verify metrics, retirement requests, and other governed records.
- Publishers expose only records that satisfy lifecycle and public-view eligibility rules.

See [Migrations](migrations.md), [Gateway](gateway.md), [Metric Verification](metric-verification.md), [Scheduler and Events](scheduler-and-events.md), and [Credit Lifecycle](credit-lifecycle.md).
