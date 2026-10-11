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

## Files

2 Python modules
