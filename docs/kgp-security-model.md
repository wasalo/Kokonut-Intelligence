# KGP Security Model

KGP has two coupled but distinct security planes:

1. PostgreSQL and governed services decide eligibility, review, accounting, and
   reconciliation.
2. The Gnosis/Chiado contracts enforce on-chain role, domain, identity,
   uniqueness, signature, pause, and upgrade controls.

Neither plane should be treated as a substitute for the other. PostgreSQL is
canonical for governed reputation facts; the contract is an auditable projection
that must reconcile against that ledger.

## Trust Boundaries

### PostgreSQL And Directus

PostgreSQL stores Guild tasks, evidence reviews, canonical reputation events,
claim state, deployment state, chain events, and canonical balances. Directus
and service workflows determine lifecycle and review state. The contract never
reads private evidence, makes eligibility decisions, or calls PostgreSQL.

### Contributor And Reviewer

Contributors can submit task evidence and, when authorized by a valid voucher,
claim points only for their own wallet. Reviewers accept, reject, dispute,
resolve, or revoke evidence through the configured review path. A review must be
accepted and governed before it becomes a KGP candidate.

### Awarder And Claim Signer

The awarder can submit automatic awards but cannot claim for arbitrary wallets or
upgrade KGP. The claim signer authorizes EIP-712 vouchers but cannot directly
invoke the awarder path. Both are operational keys that must be rotatable and
reconciled against canonical PostgreSQL records.

### Reversal Authority

The reverser is separate from ordinary awarding. Each reversal has a unique ID,
references an original award, includes reason and ledger hashes, and is bounded
by the original outstanding amount. Reversal records are append-only.

### Upgrade Authority

Upgrade authority is governance-level capability. The recommended production
holder of `UPGRADER_ROLE` is `KokonutGuildUpgradeTimelock`, not an awarder,
claim signer, contributor, or ordinary Guild steward. The timelock separates
proposer, executor, and admin roles and binds upgrades to one approved proxy.

## Contract Invariants

### Identity And Domain

- The contributor address cannot be zero.
- Award and reversal amounts must be positive.
- An award domain must be active or within its 48-hour deprecation grace period.
- The award's Guild ID must match the domain registry Guild ID.
- Reversal identity must match the original award's Guild, domain, contributor,
  and wallet.

### Non-Transferability

- `safeTransferFrom` reverts for wallet-to-wallet transfers.
- `safeBatchTransferFrom` reverts.
- `setApprovalForAll` reverts.
- Minting is limited to award/claim settlement paths.
- Burning is used for authorized reversals.

### Award Settlement

- An `awardId` can settle only once.
- Automatic award and claim paths share the same award-ID uniqueness check.
- Award records store Guild, contributor, domain, amount, outstanding amount,
  epoch, evidence hash, ledger record hash, and calculation version.
- A successful award emits `KGP_Awarded`.

### Claims

- Only the signed contributor wallet can submit its voucher.
- A voucher deadline must not have expired.
- A contributor/nonce pair can be used only once.
- The voucher chain ID must equal the executing chain.
- The recovered EIP-712 signer must hold `CLAIM_SIGNER_ROLE`.
- The voucher's award ID is still subject to the one-settlement rule.
- A successful claim emits `KGPClaimed`.

### Reversals

- A reversal ID can settle only once.
- The referenced award must exist.
- The reversal amount cannot exceed the award's outstanding amount.
- Outstanding amount is reduced before the contributor balance is burned.
- A successful reversal emits `KGPReversed` with reason, ledger, and calculation
  hashes.

### Pause Behavior

- `pause()` and `unpause()` require `PAUSER_ROLE`.
- Pausing blocks `award()` and `claim()` through `whenNotPaused`.
- `reverseAward()` is intentionally not pause-gated, allowing correction of an
  invalid balance during an incident.
- Pause state does not change existing balances or ledger history.

### Upgrade Safety

- The implementation must expose the expected UUPS `proxiableUUID`.
- The timelock only accepts the configured approved proxy.
- A queued upgrade records the expected current implementation.
- Execution fails if the proxy implementation changed after queueing.
- Execution requires the configured delay and `EXECUTOR_ROLE`.
- The proxy's storage layout must preserve balances, award mappings, reversal
  mappings, nonces, roles, domain registry, and appended state such as
  `deploymentChainId`.

## PostgreSQL Invariants

The database schema and integrity migrations enforce:

- unique award and reversal IDs;
- unique `(deployment_id, transaction_hash, log_index)` chain events;
- valid address, hash, transaction, and block formats;
- reversal events must reference an award;
- awards cannot reference reversal sources;
- canonical reputation facts are append-only and immutable;
- reversal identity must match the original award;
- cumulative reversal amount cannot exceed the original award;
- task contributor ID and wallet must match;
- chain event chain ID and contract address must match a registered deployment;
- Guild/domain/task chain identities must be paired consistently;
- negative values in `v_kgp_ledger_integrity_violations` indicate a defect.

The `v_kgp_canonical_balance` view includes only verified/published review facts
with active settlement statuses. It is the canonical balance used for
reconciliation, not a direct mirror of any one transaction.

## Candidate Safety

`v_guild_reputation_candidates` requires:

- task status `accepted`;
- evidence review status `accepted`;
- task lifecycle `verified` or `published`;
- review lifecycle `verified` or `published`.

`create_award_event()` then:

- derives a deterministic event UUID from task, epoch, and calculation version;
- derives the award ID using Solidity-compatible ABI encoding;
- requires a positive integer reward amount;
- requires evidence hash;
- inserts idempotently on award ID;
- validates immutable fields when an award-ID conflict already exists.

No database candidate should be submitted on-chain until the required human
review and reconciliation preconditions are satisfied.

## Indexer Controls

The self-hosted KGP indexer protects the projection boundary with:

- 12 confirmations by default (`KGP_CONFIRMATIONS`);
- 500-block scan batches by default (`KGP_BLOCK_BATCH`);
- deployment-specific contract address maps;
- event signature allowlisting;
- durable `kgp_chain_event` rows;
- unique transaction/log idempotency keys;
- processing states `pending`, `processed`, `rejected`, and `dead_letter`;
- durable `kgp_indexer_cursor` state;
- chain ID and contract-address identity checks;
- canonical block hash tracking;
- reorg rewind, orphan marking, projection reset, and canonical replay;
- dead-lettering when no canonical PostgreSQL event matches a chain event.

The current CLI requires `--once`; a durable worker loop is not enabled by this
command. Operators must schedule or orchestrate repeated scans with explicit
deployment and address configuration.

## Operational Controls

- Use separate keys for deployment, timelock admin, timelock proposer,
  timelock executor, KGP awarding, claim signing, reversal, pausing, and Guild
  operational roles.
- Store only evidence hashes, ledger hashes, reason hashes, CIDs, IDs, and
  timestamps on-chain. Keep private evidence off-chain.
- Record proxy, implementation, chain, deployment transaction, block, and
  upgrade authority in `kgp_protocol_deployment`.
- Persist transaction hashes, block numbers, log indexes, contract deployment
  IDs, and source chain event IDs for every projection.
- Pause award/claim settlement during RPC inconsistency, suspected key
  compromise, or reconciliation failure; use reversal authority separately for
  correction where appropriate.
- Rotate compromised operational keys through the configured role-admin and
  governance process without changing balances or historical facts.
- Require storage compatibility tests and governance approval before upgrades.
- Treat pending claims, awards, and reversals as reconciliation work rather than
  proof of final settlement.

## Guild Protocol Security

The operational Guild contracts have separate role-admin boundaries:

- the registry controls Guild identity and steward state;
- the domain registry controls domains and requires steward approval for final
  deprecation;
- the task board controls task administration and deadline state;
- evidence review controls review and dispute state;
- governance executes only allowlisted operational selectors.

Governance motions require a minimum one-day objection window, target and
selector allowlists, calldata limits, and Guild-scope matching. They cannot be
used as an implicit Moloch treasury execution path.

## Incident Recovery

If the contract or RPC is unavailable, the PostgreSQL ledger remains the
canonical recovery source. If the indexer is unavailable:

1. Preserve the durable cursor and chain-event records.
2. Restore RPC/database access.
3. Rewind after detected block-hash divergence.
4. Mark affected chain events non-canonical and orphan projections.
5. Replay canonical events in block/log order.
6. Reconcile awards, claims, reversals, balances, and deployment state.
7. Investigate dead-letter events before resuming normal settlement.

Corrections are represented by new reversal events. Destructive edits or deletes
of canonical reputation facts are rejected by database triggers.

## Verification References

Solidity tests:

```bash
cd contracts
forge test
```

Focused Python tests:

```bash
python3 -m pytest tests/test_kgp_service.py tests/test_guild_services.py tests/test_guild_reorg.py -v
```

Key implementation references:

- `contracts/src/KokonutGuildPoints.sol`
- `contracts/src/KokonutGuildUpgradeTimelock.sol`
- `schemas/postgres/317_kgp_protocol.sql`
- `schemas/postgres/318_guild_protocol_projection.sql`
- `schemas/postgres/319_guild_integrity_controls.sql`
- `services/guilds/kgp.py`
- `services/guilds/reputation.py`
- `services/guilds/indexer.py`
- `services/guilds/projections.py`
- `contracts/test/KokonutGuildPoints.t.sol`
- `contracts/test/KokonutGuildUpgradeTimelock.t.sol`
