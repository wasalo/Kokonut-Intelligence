# Pashov-Style Solidity Audit

**Date:** 2026-07-17
**Scope:** `contracts/src`, `contracts/script`, and project tests
**Compiler:** Solidity `0.8.34`
**Method:** Parallel reviews of access control, execution flow, math/invariants, integrations, deployment operations, and first-principles protocol behavior. Findings were remediated in the working tree after the review.

## Summary

| Severity | Original | Open |
| --- | ---: | ---: |
| Critical | 0 | 0 |
| High | 0 | 0 |
| Medium | 1 | 0 |
| Low | 4 | 0 |
| Informational | 3 | 3 |

## Findings

### M-01: KGP Admin Can Bypass the Upgrade Timelock (Fixed)

**References:** `contracts/src/KokonutGuildPoints.sol:127`, `contracts/src/KokonutGuildPoints.sol:328`

`initialize()` grants `DEFAULT_ADMIN_ROLE` to `admin`. OpenZeppelin `AccessControl` makes `DEFAULT_ADMIN_ROLE` the administrator of `UPGRADER_ROLE`, while `_authorizeUpgrade()` only checks `UPGRADER_ROLE`. Therefore, the KGP admin can grant `UPGRADER_ROLE` to itself or an EOA and immediately call `upgradeToAndCall`, bypassing `KokonutGuildUpgradeTimelock`.

**Impact:** A compromised or malicious KGP admin can deploy arbitrary implementation code without the documented upgrade delay or proposer/executor process. This provides complete control over KGP behavior and state.

**Recommendation:** Make the timelock the immutable or exclusive authority for upgrades. Options include overriding role administration for `UPGRADER_ROLE`, setting its role admin to a dedicated non-admin role with no externally reachable grant path, or removing admin control over `UPGRADER_ROLE` after initialization through a formally tested handoff. Add a regression test proving the KGP admin cannot upgrade directly.

**Remediation:** `UPGRADER_ROLE` is now self-administered, preventing `DEFAULT_ADMIN_ROLE` from granting or revoking it. `test_admin_cannot_grant_or_use_upgrade_role` verifies the bypass is closed.

### L-01: Unregistered Guild Steward Lookup Can Return True for Zero Address (Fixed)

**Reference:** `contracts/src/KokonutGuildRegistry.sol:101-103`

`isGuildSteward(bytes32(0), address(0))` can return true because uninitialized records have an `Active` enum value and a zero steward. Current state-changing paths guard this through active Guild checks, but external integrations could use the view directly as an authorization predicate.

**Recommendation:** Require `guild.guildId != bytes32(0)` before checking steward and status.

**Remediation:** `isGuildSteward` now requires a registered Guild record.

### L-02: KGP Does Not Validate Domain/Guild Identity Metadata (Fixed)

**References:** `contracts/src/KokonutGuildPoints.sol:135-148`, `contracts/src/KokonutGuildPoints.sol:290-316`

`award()` and signed `claim()` accept arbitrary `guildId` and `domainId` values without consulting the Guild registry or domain registry. A compromised or misconfigured awarder or claim signer can create reputation balances for nonexistent or cross-Guild identities.

**Recommendation:** If on-chain identity integrity is required, bind KGP to the domain registry and validate that the domain exists, is active, and belongs to the supplied Guild. Otherwise, document the PostgreSQL-only identity trust boundary explicitly.

**Remediation:** KGP now stores a configured `KokonutGuildDomain` registry and rejects awards or claims for inactive, nonexistent, or cross-Guild domains.

### L-03: Resolver Deployment Defaults to Celo EAS on Other Chains (Fixed)

**References:** `contracts/script/DeployKokonutResolver.s.sol:9`, `:15`, `:22-28`

The resolver deployment script defaults `EAS_ADDRESS` to the Celo mainnet address without checking `block.chainid`. Deploying on Gnosis, Chiado, or another chain without overriding the variable produces a resolver permanently bound to an address that is not the local EAS deployment.

**Impact:** Attestations and revocations fail through `SchemaResolver.onlyEAS`; the resolver must be redeployed.

**Recommendation:** Use an explicit chain-to-EAS address mapping, require an override on unsupported chains, and verify the configured address has deployed code.

**Remediation:** The script only uses the Celo default on Celo; other chains require explicit `EAS_ADDRESS` configuration and deployed-code validation.

### L-04: Guild Deployment Allows Zero Operational Role Addresses (Fixed)

**References:** `contracts/script/DeployKokonutGuildProtocol.s.sol:101-107`, `:115-130`

Production role addresses are loaded from environment variables, but only admin and bootstrap are validated as nonzero. A zero role can be granted successfully but can never operate the corresponding workflow.

**Impact:** Guild creation, reviews, governance execution, or other operational functions can be permanently disabled after deployment until the admin repairs the role configuration.

**Recommendation:** Validate every configured production role as nonzero before deployment and assert all handoff roles after deployment.

**Remediation:** Deployment now rejects zero operational role addresses before wiring the protocol.

## Informational and Hardening Observations

### I-01: Generic Upgrade Timelock Target Scope

`KokonutGuildUpgradeTimelock.queueUpgrade` accepts arbitrary proxy and implementation addresses. If the timelock is reused across systems, a proposer can schedule any compatible proxy controlled by the timelock. Bind the timelock to an immutable approved proxy or maintain an explicit target allowlist.

### I-02: Governance Emits Unbounded Returndata

`KokonutGuildGovernance.executeMotion` emits the complete return data from the target call. Future allowlisted targets returning large data can create avoidable gas pressure. Omit the data from the event or cap the emitted length.

### I-03: Test and Tooling Gaps

There are no stateful `invariant_*` tests. Coverage is 55.94% lines, 53.48% statements, 13.48% branches, and 68.69% functions; deployment scripts have 0% coverage. No fork-level EAS/resolver tests were found. `slither`, `aderyn`, `mythril`, `echidna`, and `solhint` were unavailable.

## Verification

- Before remediation, `forge test --fuzz-runs 1000`: 27 passed, 0 failed.
- After remediation, `forge test --fuzz-runs 1000`: 28 passed, 0 failed.
- `forge build --sizes`: passed.
- Largest runtime contract: KGP at 13,611 bytes.
- Solidity compiler: `0.8.34`.
- No live deployment or fork test was performed.
- Remediation changes are currently uncommitted and have not been pushed to PR 30.
