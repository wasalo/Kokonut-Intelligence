# governance

`services.governance` — Configurable Governance Framework abstraction for Kokonut Intelligence.

This package is the **on-chain DAO governance** layer. It exposes a pluggable
`GovernanceFramework` abstraction (first adapter: **Moloch v3 / Baal** on Gnosis
Chain) that reads on-chain state — proposals, votes, member shares/loot,
governance config, shamans — via the `BaalReadClient`.

**Boundary — read-first, no writes.** Adapters contain **no
transaction-submitting methods**. Proposal submission, execution, ragequit, and
shaman calls are out of scope and must route through a human-approved
Agent/Governor flow (see `services/agents/safety.py`).

## The two governance CLIs (do not confuse them)

| Surface | Package | CLI style | Backing | Meta-CLI command |
|---|---|---|---|---|
| Off-chain stakeholder/circle/tactical governance | `services/analytics/cli_governance_*.py` | argparse | PostgreSQL (`governance_*` tables) | `kokonut governance ...` |
| On-chain DAO read client (Baal/Moloch) | `services/governance/` | typer | Gnosis Chain RPC | `kokonut dao ...` |

The meta-CLI (`services/cli.py`) mounts **both**:

- `governance` → `services.analytics.cli_governance_roles` — off-chain,
  DB-backed role/circle/proposal/tension/tactical commands (argparse).
- `dao` → the typer group from this package — read-only on-chain DAO queries.

The naming is deliberate: `governance` = the platform's off-chain governed
records; `dao` = the on-chain DAO state. The two do not share code paths and
should not be merged.

## CLI Usage

```bash
python3 -m services.governance.cli --help
python3 -m services.governance.cli framework list
python3 -m services.governance.cli baal config
python3 -m services.governance.cli baal proposals
python3 -m services.governance.cli baal proposal 3
python3 -m services.governance.cli baal member 0xWALLET
python3 -m services.governance.cli baal shaman 0xSHAMAN
```

Baal event indexing lives in `services/ingestion/baal_indexer.py`.

## Modules

- `adapters` — Register concrete governance framework adapters.
- `baal` — Read-only integration client for the Kokonut DAO (Moloch v3 / Baal).
- `base` — Core types for the configurable Governance Framework abstraction.
- `cli` — Unified governance CLI for Kokonut Intelligence.
- `registry` — Framework registry: resolve a configured governance framework by key.

## Files

5 Python modules
