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
