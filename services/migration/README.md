# migration

`services.migration`

## CLI Usage

```bash
python3 -m services.migration
```
```bash
python3 -m services.migration.cli --help
```

## Explicit deployment selection

```bash
python3 -m services.migration migrate --schemas-only \
  --compose-project kokonut-kernel-portability \
  --compose-file docker-compose.kernel-portability.yml
```

Supply both options together. Repeat `--compose-file` for ordered overlays.
Explicit selection uses the repository project directory and `--env-file /dev/null`;
export required encrypted secrets beforehand. The database service is `database`.
Without these options, legacy ambient Compose selection is preserved. These options
select the destination only; checksums, ordering, locks, and transaction handling
remain enforced. No services are started by the migration CLI.

## Explicit migration selection

`migrate` accepts repeated `--only-migration` options for callers that own a
reviewed subset, such as the curated reference seeds. IDs use the full discovered
name, for example:

```bash
python3 -m services.migration migrate \
  --only-migration seed:000_expense_categories.sql \
  --only-migration seed:022_metric_governance.sql
```

The runner validates all discovered sources and applied checksums, rejects an
unknown or duplicate selected ID before applying, and preserves the order of
the supplied IDs. Omit the option to use the regular schema-first full plan.
Selection does not resolve dependencies: apply required schema migrations
first. The curated seed script does that in its schema-only pass.
When the selected list includes seed:140_mobile_forms.sql, the runner allows
either no matching form/revision rows or a full match of all source columns and
active revision snapshots. Partial or divergent state blocks the selected
batch before any member runs and is checked again under table locks in the seed
transaction. This records a verified no-op without rewriting a governed form.

## Audited historical checksum repair

The runner rejects any applied migration whose recorded SHA256 differs from
the checked-out source. A small source-controlled allowlist supports only
reviewed historical cases; the repair command additionally requires the exact
recorded old checksum, an operator/reason, and `--confirm`, then writes an audit
row to `schema_migration_repair` in the same transaction as the ledger update.
Migration SQL is never rewritten. Target-specific validation runs before the
repair. Unknown checksums remain blocked by the normal planner.

For the Kernel candidate's exact historical `schema:000_extensions.sql`
variant, both the old and current source SHA256 values are allowlisted, and the
repair requires the six expected PostgreSQL extensions to already exist. This
confirms the effect of its prior source before the current ledger fingerprint
is recorded. Use the explicit candidate Compose selection; never run this
repair against the legacy application by ambient Compose.

## Optional read-only analytics source role

`services.migration.analytics_role` is an explicit one-shot operation, separate
from ordered migrations. It requires a dedicated Kernel PostgreSQL instance and
the `analytics-admin` Compose profile. It revokes `PUBLIC CONNECT` from every
currently connectable database on that instance, removes `PUBLIC TEMPORARY` on
the target application database, and grants the login only `CONNECT`, reporting
schema `USAGE`, and `SELECT` on the three named curated views. It does not create
a Metabase source or alter the application role.

Store `KOKONUT_ANALYTICS_PASSWORD` in encrypted `.env.sops`, then run from the
repository root:

```bash
source scripts/load-secrets.sh
docker compose --env-file /dev/null -p kokonut-kernel-candidate \
  --profile analytics-admin \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-analytics-role.yml \
  run --rm analytics-role-bootstrap
```

The bootstrap validates the view owner and relations, denies source access to
application tables, the private metric-publication policy, DDL, temporary
tables, and other databases, then verifies those boundaries with a real login.
Existing extension metadata grants and extension function `EXECUTE` privileges
remain inherited from `PUBLIC`; review them for the selected PostgreSQL image.
If another database is added to the instance later, rerun the bootstrap after
review because database-level `PUBLIC CONNECT` defaults may apply again.

## Optional Metabase metadata role

`services.migration.metabase_role` provisions `kokonut_metabase_app` as the
owner of a separate `kokonut_metabase` metadata database. It does not grant
that identity access to `kokonut_intelligence`; Metabase's operational source
must use the distinct `kokonut_analytics_ro` login. The bootstrap requires the
dedicated Kernel candidate and refuses to proceed while other databases inherit
`PUBLIC CONNECT`. The metadata role receives only `CONNECT` and database-level
`CREATE` on its own database; the bootstrap verifies a real login, rolls back a
metadata table-creation probe, and checks that connection to the application
database is denied.

Store `KOKONUT_METABASE_PASSWORD` in encrypted `.env.sops`, then run:

```bash
source scripts/load-secrets.sh
docker compose --env-file /dev/null -p kokonut-kernel-candidate \
  --profile analytics-admin \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-metabase.yml \
  run --rm metabase-role-bootstrap
```

Start Metabase separately and only when needed:

```bash
docker compose --env-file /dev/null -p kokonut-kernel-candidate \
  --profile analytics \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-metabase.yml \
  up -d metabase
```

The service has a loopback-only host port and stays on the private candidate
network. On first startup, complete Metabase's local setup UI, then add a
PostgreSQL source at host `database`, port `5432`, database
`kokonut_intelligence`, using `kokonut_analytics_ro` and its SOPS-managed
password. Select only the `kokonut_reporting` schema. Do not restore or reuse
the legacy sample H2 cards as Kokonut reports.

Keep `KOKONUT_METABASE_ENCRYPTION_KEY` alongside encrypted metadata backups.
The pinned Metabase image must start with `MB_ENCRYPTION_SECRET_KEY` set before
any source credentials are registered.

This command is inappropriate for a PostgreSQL cluster shared with unrelated
applications: instance-wide PUBLIC database privileges are changed. The current
local candidate had 16 extension-owned relations with `PUBLIC SELECT`, eight
were visible to the analytics login, and 1,165 extension functions remained
executable through inherited grants. None of the public-executable extension
functions was SECURITY DEFINER. No application relation outside the three
reporting views was readable. See the [candidate evidence](../../docs/refactor/builds/2026-10-11-recovery/candidate-analytics-role.json)
and [role policy](../../docs/refactor/optional-database-roles.md).

## Apply and failure semantics

The runner applies each migration body and its `schema_migration` ledger write
inside the same transaction while holding the migration advisory lock. Existing
top-level `BEGIN`/`START TRANSACTION` and `COMMIT` wrappers are normalized into
that transaction, so a migration cannot commit its schema changes before its
tracking row. A statement failure stops `psql`; PostgreSQL rolls back the open
transaction when the session closes. Unbalanced or nested transaction markers
are rejected before execution. Migrations containing commands that cannot run
inside a transaction must not use this runner until a deliberate, separately
reviewed execution policy exists.

## Modules

- `cli` — Discover, track, and apply PostgreSQL schema and seed migrations.
- `runtime_role` — Provision the Kernel app role and separate bounded
  operator-auth login; isolate browser-session table access.
- `analytics_role` — Provision and verify the optional curated reporting-source login.
- `metabase_role` — Provision and verify the isolated optional Metabase metadata database/login.

## Files

4 Python modules
