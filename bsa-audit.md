# Behavioral State Analysis Audit

**Date:** 2026-07-17
**Scope:** `contracts/src`, deployment scripts, and Foundry tests
**Compiler:** Solidity `0.8.34`
**Baseline:** Post-remediation working tree on `feat/kgp-protocol`
**Status:** F-01 and listed hardening actions implemented in the working tree

## Behavioral Decomposition

| Contract | Type | States | Key invariants | Privileged roles | Value entry/exit |
| --- | --- | --- | --- | --- | --- |
| `KokonutGuildPoints` | Token/Proxy | paused, initialized, award records, claim nonces | non-transferable; reversal <= outstanding; valid active domain | admin, awarder, claim signer, reverser, pauser, timelock upgrader | no monetary asset flow; reputation mint/burn |
| `KokonutGuildRegistry` | Governance/Registry | active, paused, deprecated Guilds | unique Guild IDs/keys; registered steward only | admin, Guild admin | none |
| `KokonutGuildDomain` | Utility/Registry | active, paused, deprecated domains | active domain belongs to active Guild; parent Guild matches | admin, domain admin | none |
| `KokonutTaskBoard` | Utility/Lifecycle | open, assigned, submitted, accepted, rejected, disputed, cancelled, paid | contributor-only evidence; review-only decisions; paid requires accepted | admin, task admin, evidence review | reward fields are metadata only |
| `KokonutEvidenceReview` | Governance/Lifecycle | accepted, rejected, disputed, revoked | one review per task; task status mirrors review | admin, reviewer | none |
| `KokonutGuildGovernance` | Governance/DAO | open, passed, rejected, executed, cancelled | target/selector/scope allowlists; execution after objection window | admin, proposer, objector, executor | no ETH/token transfer |
| `KokonutGuildUpgradeTimelock` | Proxy Authority | queued, delayed, executed, cancelled | delay; distinct roles; one execution per ID | admin, proposer, executor | implementation control only |
| `KokonutResolver` | EAS Utility | allowed/removed attesters | only configured EAS; only allowed attesters | owner | no payable flow |

## Engine Selection

| Engine | Scope |
| --- | --- |
| ETE | KGP token accounting only; no monetary value flows found |
| ACTE | all contracts; full for governance/proxy/token, lite for utility contracts |
| SITE | all lifecycle, governance, token, proxy, and cross-contract paths |
| Advanced | KGP upgrade migration, EIP-712 claims, EAS resolver, cross-contract task/review calls |

## Findings

### [F-01] Upgrade Migration Leaves KGP Domain Registry Unset

Severity: Medium  |  Confidence: 70%

Location: `contracts/src/KokonutGuildPoints.sol#L75-L139`, `_settleAward()`; `contracts/script/UpgradeKokonutGuildPoints.s.sol#L14-L23`; `contracts/script/QueueKokonutGuildPointsUpgrade.s.sol#L8-L16`

Root Cause: The remediation added the `domainRegistry` storage field and only initializes it through the new `initialize(..., domains, ...)` path. Existing initialized proxies cannot call `initialize` again, and both upgrade scripts upgrade the implementation without invoking a migration or setting the new storage field.

Exploit:

1. Deploy or operate a proxy using the pre-remediation KGP implementation.
2. Upgrade that proxy to the current implementation through the timelock scripts.
3. Call `award()` or `claim()`.
4. `_settleAward()` calls `domainRegistry.isActiveDomain()` with a zero address and issuance reverts.

Impact: Reputation issuance is unavailable after the upgrade until a subsequent implementation provides a migration path; existing balances remain readable but new awards and claims cannot settle.

Fix: Add a one-time, role-protected migration function such as `reinitializeDomainRegistry(KokonutGuildDomain domains)` using `reinitializer(2)`, validate the registry, and make both queue/upgrade paths encode the migration call. Add a storage-layout upgrade test from the previous implementation.

**Remediation:** Implemented `reinitializeDomainRegistry` with `reinitializer(2)` and upgrader authorization. Upgrade scripts encode the migration by default and accept reviewed `KGP_UPGRADE_DATA` for later upgrades. Added an upgrade-compatible regression test that clears the appended registry slot before migration.

## Hardening Observations

- `KokonutGuildUpgradeTimelock.queueUpgrade()` accepts arbitrary proxy/implementation pairs. Bind it to the approved KGP proxy if the timelock will not be intentionally reused.
- `DeployKokonutGuildPoints` validates registry bytecode but not interface or chain identity. Validate `KokonutGuildDomain` behavior and deployment identity before initialization.
- No stateful `invariant_*` tests cover KGP conservation, task/review sequences, or upgrade migrations.
- No fork-level EAS, Gnosis, or Chiado tests were available.

**Remediation:** The timelock now stores and enforces an approved proxy. KGP deployment validates both domain and underlying Guild registry bytecode. Fork and invariant coverage remain open validation gaps.

## Verification

- Before remediation, `forge test --fuzz-runs 1000`: 28 passed, 0 failed.
- After remediation, `forge test --fuzz-runs 1000`: 30 passed, 0 failed.
- After remediation, `forge coverage`: 54.91% lines, 52.48% statements, 13.07% branches, 69.00% functions.
- `forge build --sizes`: passed.
- Python platform tests: 246 passed, 1 skipped.
- Static analyzers were not installed: Slither, Aderyn, Mythril, Echidna, and Solhint.
- Remaining hardening gaps are invariant tests and fork-level EAS/Gnosis/Chiado validation.
