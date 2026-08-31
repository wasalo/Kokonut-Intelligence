# Kokonut Treasury — SAFE Architecture

**Document:** KI-12 (SAFE Wallet Integration) · Phase A discovery
**Status:** verified on-chain 2026-08-29 (Gnosis Chain via SAFE Transaction Service)

## Overview

Kokonut uses **SAFE (safe.global)** as its custody/execution layer, integrated
with **Moloch v3 (Baal)** governance via the **DAOHaus** stack. Two distinct
SAFEs exist in the ecosystem — do not conflate them:

| SAFE | Address | Type | Controlled by |
|---|---|---|---|
| Core Team SAFE | `0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5` | Plain multisig (2-of-3) | Kokonut Core Team |
| Kokonut DAO Treasury | `0xeB55b75328a8dFfd45Bbf34B7e7efC431A179085` | Ragequittable Safe, Baal-owned | Kokonut DAO (Moloch v3 / Baal) |

Baal contract: `0x8977c56e979f0D8B76aFB5aD85549aCd2e96422d`

## On-chain discovery (verified via SAFE Transaction Service API)

### Core Team SAFE — `0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5`
- **Threshold:** 2-of-3
- **Owners (3):**
  - `0xF7E75e58Dfa8CE8f278444523d8564992F5E5322`
  - `0x535d64EB74a24883944c9A44c02a2733F929BFFF`
  - `0x0ea26051F7657d59418da186137141CeA90D0652`
- **Version:** Safe v1.4.1+L2
- **Modules:** none · **Guard:** none
- **Nonce:** 7 (active; recent txns show 2/2 confirmations)
- **Role in KI:** EAS Resolver owner (`KOKONUT_MULTISIG`), governance attestations

### Kokonut DAO Treasury — `0xeB55b75328a8dFfd45Bbf34B7e7efC431A179085`
- **Threshold:** 1
- **Owners:** `0x8977c56e979f0D8B76aFB5aD85549aCd2e96422d` — **the Baal contract itself**
- **Modules:** `0x8977c56e979f0D8B76aFB5aD85549aCd2e96422d` — **Baal as Zodiac module**
- **Version:** Safe v1.3.0
- **Nonce:** 0 (fresh; no multisig txs yet)
- **Role in KI:** `treasury` in `KOKONUT_BAAL_ADDRESSES` (`services/ingestion/config.py`)

> **Key confirmation (DAOHaus model):** the treasury SAFE's owner AND its
> module are both the Baal contract. Governance (proposals/votes) happens in
> Baal; execution flows through the SAFE. This matches the DAOHaus docs:
> *"Proposals are executed through Gnosis safe multicall function execution."*

## KI integration surface

KI already reads the **governance half** (Baal proposals/votes/members) via
`services/governance/baal.py` (`BaalReadClient`). The **missing half** is the
**SAFE treasury side** — this is what `services/treasury/` adds.

### Read model (mirrors governance read-first pattern)
- SAFE config: owners, threshold, modules, guards, version
- Balances: native + ERC-20 (+ ERC-721/1155 where relevant)
- Transactions: pending (proposed/confirmed), executed, nonce
- Per-farm SAFEs (sidecars) once Phase C provisions them

### Write model (human-gated, Phase C)
- **Agent proposes** a farm SAFE via `services/treasury/provisioning.py`
  (`propose_farm_safe`): location_id, chain, steward addresses, threshold →
  inserts a `safe_account` row with `provisioning_status='proposed'`,
  `status='draft'`.
- **Human approves** (`approve_farm_safe`): advances to `approved`/`verified`,
  or `active`/`published` once the SAFE Factory deployment returns a real
  address.
- **SAFE "propose function role"** gives the agent the ability to *propose*
  transactions on the deployed SAFE; only humans sign/execute.
- Farm provisioning uses the **official SAFE Factory + APIs** — no custom
  deployments.

### Schema (Phase C, migration 354)
- `safe_account`: SAFE registry — address, chain, role
  (core_team/dao_treasury/farm), location_id/farm_id links, threshold,
  owners, modules, provisioning_status (proposed→approved→deployed→active),
  governed lifecycle. Seeded with the two canonical Kokonut SAFEs.
- `safe_transaction`: indexed SAFE multisig txs for reporting/evidence,
  governed lifecycle.

### CLI (mounted in meta-CLI as `kokonut treasury …`)
```
kokonut treasury status                     # both SAFEs' config
kokonut treasury balances --address 0x…     # token balances
kokonut treasury transactions --limit 10    # multisig tx history
kokonut treasury propose <location_id> --stewards A,B --threshold 2
kokonut treasury approve <safe_id> --safe-address 0x…   # human gate
kokonut treasury farms [--location-id …]    # farm SAFEs
kokonut treasury ops-propose <safe_id> <to> --value 1.5 --memo "payroll"  # agent proposes farm op
```

## Write-path (Phase D — KI-14)

The server holds a **delegate key that can only propose** transactions via the
SAFE Transaction Service API (never signs/executes). Humans confirm in the
Safe app. Even a full delegate-key leak can only propose, never move funds.

### Attestation signing via SAFE (D2, Celo)
`services/attestation/safe_flow.py`: builds the EAS `attest()` call
(`EASClient.build_attest_call`), wraps it in a Safe tx, and proposes it to the
Core Team SAFE on Celo. `reconcile_attestation_executions()` marks requests
executed once humans confirm. `ATTESTER_PRIVATE_KEY` is now propose-only.

### Escrow settlement via SAFE (D3, Gnosis)
`services/credit_class/safe_settlement.py`: marketplace value moves (credit
transfer seller→buyer, fee→treasury) are proposed as Safe txs on the Core
Team SAFE (2-of-3) instead of raw DB-only escrow updates. Order book stays in
DB as source of truth; `safe_transaction` indexes the proposals.

### Farm treasury ops (D4)
`services/treasury/ops.py`: the agent proposes ops (payroll, inputs, expenses)
on a deployed farm SAFE (from Phase C provisioning); farm stewards confirm.
Address/chain resolve from the `safe_account` record.

### Security invariant
Agent (delegate) proposes → humans confirm → SAFE executes. The delegate key
is propose-only at the Safe contract level; execution requires m-of-n human
signatures on the SAFE.

## Chain strategy (chain-agnostic)

Kokonut Ecosystem is **chain agnostic** — different farms/teams/communities
choose their chain. SAFE is deployed on many chains, which fits.

| Chain | Role |
|---|---|
| Gnosis | Kokonut DAO (Baal + treasury SAFE) |
| Celo | EAS attestations (primary attestation chain) |
| Ethereum | SAFE template canonical deployment |
| Any SAFE-supported chain | Farm SAFEs / experiments as needed |

`services/treasury/` must be chain-agnostic from day one: config maps
chain_id → SAFE API base URL (mirrors the governance adapter pattern).

## Design principle

> *"The Kokonut Ecosystem should be chain agnostic… we need the freedom to
> select/configure governance framework, economics, or farm design tailored to
> the needs of the people developing that specific location, project or farm."*

The treasury module follows the same modular philosophy as
`services/governance/adapters.py`: no hardcoded chain, no single-framework
assumption. Farms may be inside the Kokonut DAO (Gnosis) or standalone with
their own SAFE — the platform must support both.

## References

- SAFE: https://safe.global · https://docs.safe.global
- DAOHaus: https://docs.daohaus.club (Treasury/Safe contracts)
- KI config: `services/ingestion/config.py` (`KOKONUT_BAAL_ADDRESSES`)
- KI governance: `services/governance/baal.py`, `services/governance/adapters.py`
- KI attestation: `services/attestation/config.py` (`KOKONUT_MULTISIG`)
