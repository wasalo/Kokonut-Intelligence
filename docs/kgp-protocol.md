# Kokonut Guild Points Protocol

## Purpose

Kokonut Guild Points (KGP) are a non-transferable, domain-scoped reputation unit for contributors to Kokonut Guilds. KGP recognizes reviewed work and evidence; it is not money, a payment instrument, or a substitute for Moloch DAO governance.

The protocol is self-hosted and deployed on Gnosis Chain. PostgreSQL is the canonical source of truth for governed contribution and reputation records. The KGP contract is an auditable on-chain projection and a settlement layer for automatic awards and contributor claims.

## Separation of Powers

- Moloch DAO controls treasury assets, `$vKKN`, Loot, rage-quit, and treasury proposals.
- Guilds coordinate operational work, review contributions, and maintain domain reputation.
- KGP does not grant Moloch voting power and cannot invoke treasury actions.
- Celo EAS remains the attestation layer for farm and MRV evidence.
- PostgreSQL determines eligibility, review status, calculation version, and canonical balances.
- Gnosis records award, claim, and reversal commitments with transaction history.

## Reputation Properties

Every reputation event is:

- Scoped to one Guild domain.
- Assigned to one contributor wallet.
- Linked to a reviewed evidence commitment.
- Recorded as an append-only award or reversal event.
- Versioned by epoch and calculation version.
- Corrected through an explicit reversal, never an in-place edit.
- Non-transferable and non-delegable.

The canonical balance is the PostgreSQL sum of accepted, non-reversed events. The on-chain balance is a public projection that must reconcile against that ledger.

## Domain-Scoped Representation

KGP uses an ERC-1155-compatible domain balance model rather than ERC-20. Each domain has a stable token identifier. A contributor's balance is queried as:

```text
balanceOf(contributor, domainId)
```

Wallet-to-wallet transfers, approvals, and operator transfers are disabled. Minting and burning are protocol actions performed only by authorized award and reversal paths.

## Award Lifecycle

### Automatic Award

1. A contribution is submitted to PostgreSQL.
2. Required human review accepts the contribution and its evidence.
3. PostgreSQL creates a canonical reputation event and deterministic `awardId`.
4. An authorized Kokonut awarder submits the event commitment on-chain.
5. The indexer records the transaction and block reference.
6. The reconciliation process compares the on-chain event with PostgreSQL.

### Claimable Award

1. PostgreSQL accepts a canonical reputation event.
2. An authorized Kokonut signer creates an EIP-712 claim voucher.
3. The contributor submits the voucher from the recipient wallet.
4. The contract validates the signer, recipient, nonce, deadline, and award ID.
5. The contract records the award and mints the non-transferable domain balance.
6. PostgreSQL records the claim transaction and reconciles the event.

Automatic awards and claims consume the same unique `awardId`; they cannot both settle the same award.

## Reversal Lifecycle

A correction creates a new reversal event referencing the original award:

```text
award A -> reversal R -> optional corrected award B
```

A reversal must identify the original award, amount, reason commitment, PostgreSQL ledger record, and calculation version. Reversal amount cannot exceed the unreversed amount of the original award. Historical events remain queryable.

## Contract Authority

- `AWARDER_ROLE` submits approved automatic awards.
- `CLAIM_SIGNER_ROLE` authorizes claim vouchers but cannot directly mint.
- `REVERSER_ROLE` submits governed correction events.
- `PAUSER_ROLE` stops state-changing award, claim, and reversal operations during incidents.
- `UPGRADER_ROLE` authorizes UUPS implementation upgrades.

Production upgrade authority must be transferred from the deployment operator to Kokonut governance, preferably through an approved Moloch DAO execution or the Kokonut multisig during bootstrap. The awarder service must never control upgrades.

## Identifier Rules

`awardId` and `reversalId` are deterministic, unique identifiers derived from canonical PostgreSQL identity and calculation context. Full evidence and private data remain off-chain. The contract stores compact hashes and identifiers:

```text
awardId = keccak256(guildId, domainId, contributor, ledgerEventId, calculationVersion)
```

The exact ABI-encoded derivation is part of the contract interface and must be shared by PostgreSQL services and tests.

## Versioning

The contract is UUPS-upgradeable. Upgrades must preserve balances, consumed award IDs, reversal state, role boundaries, and event compatibility. Storage layout changes require an upgrade test from the previous implementation.

Claim voucher domain version changes invalidate outstanding vouchers and therefore require an explicit protocol migration. No implementation may silently change the signing domain.

## Non-Goals

KGP does not provide:

- Transferable value.
- Treasury ownership.
- Moloch voting rights.
- Automatic truth about off-chain evidence.
- Permission to publish or verify governed records without human review.
- A replacement for `$vKKN` or Loot.
