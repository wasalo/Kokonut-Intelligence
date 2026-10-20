# Unified CLI Kernel contract

**Status:** the command tree is deployed; common registration/help/forwarding
checks pass. Full module-level legacy CLI parity remains open.

## Entry points

`python3 -m services.cli` is the unified entry point. Native Typer groups such
as `kernel`, `dao`, and `treasury` stay native. The legacy argparse commands in
`services.cli._MOUNTED` are registered through the shared `mount_argparse`
adapter, which forwards trailing arguments to each legacy `main()` and restores
the caller's `sys.argv`, including when parsing raises `SystemExit`.

The outer Typer command owns `--help`; use an argument separator to invoke the
legacy parser's own help, for example:

```sh
python3 -m services.cli agents -- --help
```

The registered agent task catalogue supports a database-free list command:

```sh
python3 -m services.cli agents list
```

## Verification

`tests/test_cli.py` checks that all mounted command names appear in root help,
every mounted wrapper displays help, and each registered adapter forwards a
synthetic unknown option and positional value to its own legacy `main()` while
restoring `sys.argv`. It also executes the offline agent catalogue list and
legacy argparse help through the unified command tree. A subprocess sweep
invokes actual parser help for all 37 mounted argparse groups with an
intentionally unavailable SOPS key; every parser exits successfully without
attempting secret decryption.

A second subprocess sweep sends an invalid non-help option through all 37
mounted parsers with an unavailable SOPS key and a closed loopback PostgreSQL
port. Every group rejects it with argparse usage/error output and exit code 2
before secret decryption or database connection. The ingestion wrapper now
rejects unknown top-level arguments instead of printing help and returning
success; no-argument help and `--list` remain available. See the
[preflight evidence](builds/2026-10-19-recovery/cap-039-invalid-argument-preflight.json).

The legacy module imports are intentionally lazy. CAP-038 moved agent audit
database imports behind the explicit audit-write call so task listing does not
decrypt secrets. `services.common.db` also skips secret loading when an explicit
`-h` / `--help` token is present; help exits before any database operation.
This source slice does not invoke databases or providers.

## Successful offline command parity sample

The first success-path parity group compares standalone module output with its
mounted unified command using the same arguments. It covers:

| Mounted group | Successful invocation | Dependency classification | Output boundary |
| --- | --- | --- | --- |
| `agents` | `list` | Local task catalogue; no database or provider | Newline-delimited registered task keys |
| `ingestion` | `--list` | Local static registry; no database or provider | Sorted tool names and descriptions |
| `mobile-forms` | `validate --manifest <synthetic-file>` and `preview --manifest <synthetic-file>` | Local file and schema validation; no database or provider | JSON summary reports `database_write: false`; preview reports `publication: not applied` |
| `audit-spool` | `status --path <missing-private-path>` | Local SQLite capacity check; no PostgreSQL or provider; missing-file status does not create the journal | JSON capacity summary; no journal contents |
| `systems` | `--list-modules` | Local Python module registry; no database or provider | Sorted module names and descriptions |
| `capability-map` | `list --status active` | PostgreSQL read through the capability-map service; the query is stubbed in this test | JSON capability rows |
| `stakeholders` | `list --party-type organization` | PostgreSQL read; connection and query are stubbed in this test | JSON party rows |
| `strategy-map` | `list --perspective financial` | PostgreSQL read through strategy-map service; query is stubbed in this test | JSON strategy rows |
| `value-stream-defs` | `list --stakeholder farmer` | PostgreSQL read through value-stream service; query is stubbed in this test | JSON value-stream rows |
| `vision-mission` | `current --entity-type organization` | PostgreSQL read through vision/mission service; query is stubbed in this test | JSON current statement rows |
| `technology-roadmap` | `list --entity-type location` | PostgreSQL read through roadmap service; query is stubbed in this test | JSON roadmap rows |

For each row, the regression invokes both `python -m <legacy-module>` and
`python -m services.cli <group> -- ...`, then compares exit status and output.
The form fixture is synthetic, and the spool path is a fresh temporary path.
The test environment sets an unavailable SOPS identity and a closed loopback
PostgreSQL URL so accidental secret/database setup fails instead of reaching a
real service. Six successful offline invocations and six PostgreSQL-backed
read invocations with stubbed query functions match their standalone output
across 11 mounted groups (22 tests including the native Typer command-tree
comparison below). See [the test](../../tests/test_unified_cli_success_contract.py)
and [the recorded evidence](builds/2026-10-20-recovery/cap-039-offline-success-parity.json).

The native Typer command tree is also compared between standalone and unified
registration for `kernel`, `dao`, and `treasury`, including child command
names, help text, argument types, required flags, and option names. The unified
root deliberately disables shell completion, so the standalone groups'
`--install-completion` and `--show-completion` root options are excluded from
the comparison. The check inspects command metadata only; it does not invoke a
database or chain/provider command. These checks run with the offline output
parity cases in a 22-test selection ([tests](../../tests/test_cli.py) and
[evidence](builds/2026-10-20-recovery/cap-039-offline-success-parity.json)).

The six database-backed success paths exercise their real parsers, forwarding,
and JSON renderers from both entry points with synthetic query results. The
stakeholder command also uses a fake connection and proves it closes the
connection. The cases confirm parsed filters reach the expected service calls;
they do not claim database query behavior or authorization.

This closes successful output parity only for these six offline command
invocations across five mounted groups plus six stubbed database-backed paths.
The other 26 mounted groups still need command-specific success-path checks and
database/provider classification. Privileged operator action boundaries and
MAN-CAP-039 owner acceptance are also open.

## Remaining parity gates

The invalid-option preflight proves rejection behavior only. It does not prove
successful module-specific non-help arguments, output parity, database/provider
operation, or operator authorization. Those remain to be exercised per command
in isolated groups. Module-specific commands should declare whether they
require a database, provider, or operator authorization. The unified CLI does
not itself grant authorization to a legacy command. MAN-CAP-039 remains open
until those checks and operator review are complete.
