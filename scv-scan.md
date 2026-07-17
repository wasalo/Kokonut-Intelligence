# Solidity Security Audit

**Date:** 2026-07-17
**Scope:** `contracts/src`, `contracts/script`, `contracts/test`, and Foundry configuration
**Excluded:** Vendored OpenZeppelin and Forge dependencies, except for integration behavior
**Method:** Manual entry-point and semantic review, vulnerability-pattern sweep, Foundry build/tests, and deployment-script review. Findings were remediated in the working tree after the initial audit.

## Summary

| Severity | Count |
| --- | ---: |
| Critical | 0 |
| High | 0 |
| Medium | 3 (fixed in working tree) |
| Low | 2 |
| Informational | 3 |

## Findings

### M-01: Nonexistent Guild IDs Are Treated as Active (Fixed)

**Files:** `contracts/src/KokonutGuildRegistry.sol:96-98`, `contracts/src/KokonutGuildDomain.sol:49-61`

**Description:** `isActiveGuild` checks only the enum value in the mapping. The zero value of an uninitialized `GuildStatus` is `Active`, so any unregistered nonzero Guild ID is considered active. `createDomain` therefore accepts domains for Guilds that were never registered. Those domains pass `isActiveDomain` and can be used to create and operate tasks.

**Impact:** The registry is not authoritative for Guild identity. A domain administrator can create active domain/task records outside a registered Guild, breaking Guild-scoped authorization and canonical identity assumptions.

**Recommendation:** Require existence before status checks:

```solidity
function isActiveGuild(bytes32 guildId) external view returns (bool) {
    Guild storage guild = _guilds[guildId];
    return guild.guildId != bytes32(0) && guild.status == GuildStatus.Active;
}
```

Add regression tests for arbitrary unregistered IDs and `bytes32(0)`.

**Remediation:** Implemented the existence check and added `test_unregistered_guild_cannot_create_domain`.

### M-02: Production Deployment Does Not Enforce Bootstrap Authority Separation (Fixed)

**Files:** `contracts/script/DeployKokonutGuildProtocol.s.sol:88-100`, `contracts/script/DeployKokonutGuildProtocol.s.sol:126-139`, `contracts/script/DeployKokonutGuildPoints.s.sol:21-36`

**Description:** The Guild deployment derives `bootstrap` from the deployer private key and only revokes bootstrap roles when `bootstrap != admin`. If the configured admin equals the deployer, the deployer retains administrative authority. Optional operational roles also default to the admin. The KGP deployment similarly accepts arbitrary role addresses without asserting that the deployer is not an admin, awarder, reverser, pauser, or signer.

**Impact:** A production deployment can silently leave an EOA deployment key with permanent authority to grant roles, change protocol state, mint KGP, reverse awards, pause the system, or control governance. This defeats the documented bootstrap handoff if configuration is incomplete or mistaken.

**Recommendation:** For Gnosis and Chiado deployments, require `bootstrap != admin`, require all production role addresses to be explicitly supplied, and assert the deployer is not any privileged role. Prefer Foundry `--account`/`--sender` or an external signer instead of passing private keys into scripts.

**Remediation:** Guild deployment now requires an explicit bootstrap address distinct from admin and explicit production role addresses. KGP deployment requires an explicit deployer address that cannot hold a privileged role. Scripts use Foundry account/sender selection instead of raw private-key environment variables.

### M-03: Pending Motions Ignore Later Selector and Guild-Scope Revocations (Fixed)

**File:** `contracts/src/KokonutGuildGovernance.sol:152-158`

**Description:** `createMotion` validates the target, selector, and Guild scope when a motion is created. `executeMotion` later rechecks only `allowedTargets[target]`; it does not recheck `allowedSelectors[target][selector]` or `_matchesGuild`. Consequently, a motion created under an old permission can still execute after the selector or Guild-scope policy is revoked.

**Impact:** Emergency policy revocation does not reliably stop already queued operations. A previously approved motion can execute after administrators have disabled the exact selector or scope that made it permissible.

**Recommendation:** Revalidate the selector and Guild scope during execution, or invalidate affected open/passed motions when permissions change. Add tests that revoke a selector and Guild scope after motion creation and assert execution reverts.

**Remediation:** Execution now revalidates target, selector, and Guild scope. Added `test_governance_rechecks_selector_permission_before_execution`.

## Low-Severity Findings

### L-01: Upgrade Timelock Does Not Enforce Distinct Authorities (Fixed)

**File:** `contracts/src/KokonutGuildUpgradeTimelock.sol:36-43`

**Description:** The constructor permits `admin`, `proposer`, and `executor` to be the same address. The documented operational separation is not enforced on-chain.

**Impact:** A configuration error can collapse upgrade administration, proposal, and execution into one authority. The delay remains in place, so this is not an immediate bypass.

**Recommendation:** Reject duplicate authority addresses for production deployments, or use explicit governance configuration with a multisig admin and separate proposer/executor roles.

**Remediation:** The constructor now rejects duplicate admin, proposer, and executor addresses and has a regression test.

### L-02: Deployment Scripts Consume Raw Private Keys from Environment Variables (Fixed)

**Files:** `contracts/script/DeployKokonutGuildProtocol.s.sol:89`, `contracts/script/DeployKokonutGuildPoints.s.sol:21`, `contracts/script/DeployKokonutResolver.s.sol:20`, `contracts/script/QueueKokonutGuildPointsUpgrade.s.sol:12-13`, `contracts/script/ExecuteKokonutGuildPointsUpgrade.s.sol:11`

**Description:** Production scripts load private keys with `vm.envUint` and pass them to `vm.startBroadcast`.

**Impact:** Environment leakage, shell history, CI diagnostics, or process inspection can expose deployment, upgrade, or operational signing keys.

**Recommendation:** Use Foundry keystores, hardware wallets, Safe/multisig execution, or `forge script --account ... --sender ...`. Keep private keys out of script environment variables.

**Remediation:** Project deployment and upgrade scripts now use `vm.startBroadcast()` and document `--account`/`--sender` usage.

## Informational Findings

### I-01: Solidity Compiler Version Is Behind the Recommended Baseline

**Files:** `contracts/foundry.toml:5` and all project Solidity files

The project now pins Solidity `0.8.34`, with compatibility verified by the full Foundry build and test suite.

### I-02: No Stateful Invariant Tests Are Present

**Scope:** `contracts/test`

The current suite has 24 passing tests, including fuzzed resolver coverage, but no `invariant_*` tests. Add invariants for KGP conservation, reversal bounds, non-transferability, Guild/domain identity, task state transitions, and governance motion finality.

### I-03: Static Analysis Tools Were Unavailable

`slither`, `aderyn`, `mythril`, `echidna`, and `solhint` were not installed. The conclusions above are based on manual review and Foundry verification; static analyzer results should be collected before deployment.

## Verification

- `forge build --sizes`: passed; largest runtime contract was KGP at 13,601 bytes.
- `forge test --fuzz-runs 1000`: 27 passed, 0 failed.
- No invariant tests were found.
- No live deployment or fork test was performed.
- Audit remediation changes are present in the working tree and have not yet been committed.
