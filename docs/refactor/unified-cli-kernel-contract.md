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

## Remaining parity gates

The invalid-option preflight proves rejection behavior only. It does not prove
successful module-specific non-help arguments, output parity, database/provider
operation, or operator authorization. Those remain to be exercised per command
in isolated groups. Module-specific commands should declare whether they
require a database, provider, or operator authorization. The unified CLI does
not itself grant authorization to a legacy command. MAN-CAP-039 remains open
until those checks and operator review are complete.
