# Kokonut Guild Points Protocol

Kokonut Guild Points (KGP) are non-transferable, domain-scoped reputation
points for contributors to Kokonut Guilds. KGP recognizes governed work and
reviewed evidence. It is not money, a payment instrument, a transferable token,
or a replacement for Moloch DAO governance.

The protocol is self-hosted. PostgreSQL is the canonical governed ledger for
tasks, evidence reviews, reputation events, claims, and canonical balances. The
KGP contract is an auditable on-chain projection and settlement surface for
approved awards, contributor claims, and reversals.

The repository contains deployable contracts and workflows for Gnosis Chain and
Chiado. A deployment is not considered active until its addresses, transaction
metadata, role configuration, and indexer state are recorded in
`kgp_protocol_deployment` and independently reconciled.

## Separation Of Powers

- Moloch DAO controls treasury assets, `$vKKN`, Loot, rage-quit, and treasury
  proposals.
- The operational Guild protocol coordinates Guilds, domains, tasks, evidence
  review, and allowlisted governance motions.
- KGP awards reputation points but grants no Moloch voting power and cannot call
  Moloch treasury execution.
- Celo EAS remains the attestation layer for farm and MRV evidence.
- PostgreSQL determines candidate eligibility, review state, calculation
  version, settlement state, and canonical balances.
- Gnosis or Chiado records KGP award, claim, reversal, and operational protocol
  events as an auditable projection.

## Contract Model

`KokonutGuildPoints` is:

- ERC-1155-compatible for domain balances;
- UUPS-upgradeable behind an ERC-1967 proxy;
- EIP-712-enabled for claim vouchers;
- role-controlled through OpenZeppelin AccessControl;
- pausable for award and claim incident response;
- domain-aware through `KokonutGuildDomain`.

Each active domain has a numeric token ID. A contributor balance is queried as:

```solidity
balanceOf(contributor, domainId)
```

The convenience method `domainBalance(contributor, domainId)` returns the same
value.

Wallet transfers, batch transfers, and operator approvals revert with
`NonTransferable`. Minting occurs through automatic awards or valid claims;
burning occurs through authorized reversals.

## Reputation Facts

Every canonical reputation event is:

- scoped to a Guild domain;
- assigned to a contributor wallet;
- linked to evidence and a ledger record hash;
- recorded as an append-only award or reversal event;
- identified by epoch and calculation version;
- corrected through a new reversal event rather than an in-place edit;
- represented by a unique award or reversal ID.

The PostgreSQL canonical balance view sums award amounts and subtracts reversal
amounts for events with review status `verified` or `published` and settlement
status in `pending`, `submitted`, `settled`, `reconciled`, or `reversed`.
It is the canonical accounting view; the chain balance is a projection that must
be reconciled against it.

## Guild And Domain Preconditions

The on-chain domain registry validates every award:

1. The domain must be active, or within its 48-hour deprecation grace period.
2. The domain must belong to the supplied Guild ID.
3. The contributor and amount must be nonzero.
4. The award ID must not already be settled.

Guilds and domains are separate operational records. The registry rejects
duplicate Guild IDs and keys, requires a steward, and tracks active, paused, and
deprecated status. Domain deprecation requires Guild steward approval after the
deprecation request.

## Award Lifecycle

### Candidate And Canonical Ledger

1. A Guild task is created for an active domain with an evidence requirement and
   deadline.
2. A contributor is assigned and submits an evidence hash.
3. A reviewer accepts, rejects, disputes, resolves, or revokes the evidence.
4. Accepted task/evidence pairs appear in `v_guild_reputation_candidates` only
   when task and review lifecycle states are `verified` or `published`.
5. PostgreSQL creates an idempotent `guild_reputation_event` with settlement
   method `automatic` or `claim`.
6. The service validates a positive integer reward amount and evidence hash.
7. A deterministic award payload is generated for settlement.

### Automatic Award

1. A human-reviewed candidate becomes a canonical PostgreSQL award event.
2. The authorized awarder submits the award commitment on-chain.
3. The contract validates role, domain/Guild identity, contributor, amount, and
   award-ID uniqueness.
4. The contract stores the award record and mints the domain balance.
5. `KGP_Awarded` is indexed with transaction, block, and log metadata.
6. PostgreSQL moves the event through submitted, settled, and reconciled states
   as appropriate.

Automatic award calls are blocked while KGP is paused.

### Claimable Award

1. PostgreSQL creates a canonical event with settlement method `claim`.
2. An authorized claim signer creates an EIP-712 voucher.
3. The contributor submits the voucher from the signed contributor wallet.
4. The contract checks deadline, sender, nonce, chain ID, and signer role.
5. The contract settles the shared award ID and mints the domain balance.
6. The indexer records `KGPClaimed` and updates the `kgp_claim` projection.

Automatic awards and claims share the same unique `awardId`; they cannot both
settle the same award.

## Award Identity And Voucher Encoding

The Solidity helper computes:

```text
awardId = keccak256(
  abi.encode(guildId, domainId, contributor, ledgerEventId, calculationVersion)
)
```

This uses ABI encoding, not packed encoding. The Python helper in
`services.guilds.kgp.compute_award_id()` matches the contract.

The EIP-712 `ClaimVoucher` contains:

```text
awardId
guildId
contributor
domainId
amount
epoch
evidenceHash
ledgerRecordHash
calculationVersion
nonce
deadline
chainId
```

The signing domain is `Kokonut Guild Points`, version `1`, with the target chain
ID and verifying proxy address. Changing the domain version invalidates
outstanding vouchers and requires an explicit migration.

## Reversal Lifecycle

A correction creates a new reversal event:

```text
award A -> reversal R -> optional corrected award B
```

On-chain `reverseAward()` requires the reverser role, a unique reversal ID, a
known award, a positive amount, and an amount no greater than the award's
outstanding amount. It reduces outstanding points and burns the contributor's
domain balance. A burn can fail if the contributor no longer has enough balance.

PostgreSQL additionally requires the reversal to reference an award with the
same Guild, domain, contributor, and wallet, and prevents cumulative reversals
from exceeding the original amount. Historical records remain queryable.

Reversals remain available while KGP is paused so incident correction can still
reduce an invalid balance. This is intentional and differs from award/claim
pause behavior.

## Operational Guild Protocol

The separate operational protocol contains:

| Contract | Responsibility |
|---|---|
| `KokonutGuildRegistry` | Guild identity, key, steward, and status |
| `KokonutGuildDomain` | Guild-scoped domains and deprecation workflow |
| `KokonutTaskBoard` | Tasks, assignments, deadlines, evidence submission, and task state |
| `KokonutEvidenceReview` | Evidence decisions, disputes, resolution, and revocation |
| `KokonutGuildGovernance` | Allowlisted operational motions with objection windows |

The task board and evidence review do not move treasury funds. The PostgreSQL
projection records tasks, reviews, motions, and KGP candidates while Moloch
treasury operations remain a separate governance path.

Operational controls include a 7-day review grace period, up to three disputes
per review, a 24-hour dispute cooldown, and a minimum one-day governance
objection window.

## Governance Motions

`KokonutGuildGovernance` is a lazy-consensus operational governance contract.
It can execute only:

- an allowlisted target;
- an allowlisted function selector;
- calldata of at most 256 bytes;
- a Guild-scoped call whose encoded target Guild matches the motion Guild;
- a motion that passed after the objection deadline.

Return data is bounded to 4096 bytes. The contract cannot execute arbitrary
treasury calls and does not replace a Moloch proposal.

## Contract Roles

| Role | Capability |
|---|---|
| `AWARDER_ROLE` | Submit approved automatic awards |
| `CLAIM_SIGNER_ROLE` | Sign claim vouchers; cannot directly mint through `award` |
| `REVERSER_ROLE` | Submit correction/reversal events |
| `PAUSER_ROLE` | Pause/unpause award and claim settlement |
| `UPGRADER_ROLE` | Authorize UUPS upgrades, normally held by the timelock |
| `DEFAULT_ADMIN_ROLE` | Administrative metadata and role-admin capabilities, subject to role-admin configuration |

The awarder service must not control upgrades. Production upgrade authority
should be held by the approved `KokonutGuildUpgradeTimelock` and governed through
the configured proposer/executor/admin separation.

## Versioning And Upgrades

KGP uses UUPS upgrades through the proxy. Upgrades must preserve:

- balances;
- award records and consumed award IDs;
- reversal state;
- used claim nonces;
- role boundaries;
- domain registry linkage;
- event compatibility.

The timelock checks the approved proxy, UUPS `proxiableUUID`, expected current
implementation, configured delay, and executor role before calling
`upgradeToAndCall`. The first domain-registry migration uses
`reinitializeDomainRegistry`; later upgrades use reviewed calldata.

## Non-Goals

KGP does not provide:

- transferable value or wallet-to-wallet movement;
- treasury ownership or treasury execution;
- Moloch voting rights;
- automatic truth about off-chain evidence;
- permission to verify or publish governed records;
- a replacement for `$vKKN` or Loot;
- an autonomous blockchain execution path for PostgreSQL candidates.

## References

- `contracts/src/KokonutGuildPoints.sol`
- `contracts/src/KokonutGuildDomain.sol`
- `contracts/src/KokonutGuildRegistry.sol`
- `contracts/src/KokonutTaskBoard.sol`
- `contracts/src/KokonutEvidenceReview.sol`
- `contracts/src/KokonutGuildGovernance.sol`
- `schemas/postgres/317_kgp_protocol.sql`
- `schemas/postgres/318_guild_protocol_projection.sql`
- `schemas/postgres/319_guild_integrity_controls.sql`
- `services/guilds/kgp.py`
- `services/guilds/reputation.py`
- `tests/test_kgp_service.py`
- `tests/test_guild_services.py`
