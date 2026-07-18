# KGP Security Model

## Trust Boundaries

### PostgreSQL and Directus

PostgreSQL is the canonical governed ledger. Directus workflows and services determine whether a contribution is accepted, disputed, published, or reversed. The contract does not inspect private evidence or make eligibility decisions.

### Awarder and Claim Signer

The awarder and claim signer are operational keys. They can settle approved records but cannot upgrade the contract or access Moloch treasury funds. Keys must be rotatable and all actions must be reconciled against canonical ledger records.

### Reversal Authority

Reversal authority is separate from ordinary awarding. Every reversal requires a canonical correction record and an explicit reason commitment. Reversal actions are append-only and auditable.

### Upgrade Authority

Upgrade authority is a governance-level capability. It must not be held by the awarder service, claim signer, or ordinary Guild steward. Production upgrades require contract review, compatibility tests, and an approved governance execution.

## Required Invariants

- Nonzero wallet balances cannot move between wallets.
- An `awardId` can settle at most once.
- A claim voucher can be consumed at most once.
- A claim can only mint to its signed contributor wallet.
- Expired or invalid vouchers are rejected.
- A reversal cannot exceed an original unreversed award.
- Unauthorized roles cannot award, reverse, pause, or upgrade.
- Pausing blocks state-changing settlement operations.
- Upgrades preserve all reputation state.
- KGP has no callable path to Moloch treasury execution.
- PostgreSQL reconciliation can identify every on-chain award, claim, and reversal.

## Operational Controls

- Use separate keys for deployment, awarding, claiming, reversal, and upgrades.
- Store only hashes, CIDs, IDs, and timestamps on-chain; never store private evidence.
- Persist transaction hashes, block numbers, log indexes, and contract version for every projection.
- Process events with durable cursors, confirmation depth, idempotency, and replay support.
- Pause settlement during RPC inconsistency, suspected key compromise, or reconciliation failure.
- Revoke compromised roles through governance and rotate keys without changing balances.
- Run Foundry unit, fuzz, invariant, upgrade, and fork tests before Chiado deployment.

## Incident Recovery

The canonical PostgreSQL ledger remains recoverable if the contract or indexer is unavailable. After recovery, the indexer replays confirmed blocks and reconciliation identifies missing or divergent events. Corrections are represented by new reversal events rather than destructive edits.
