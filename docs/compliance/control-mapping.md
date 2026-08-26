# Control Mapping — SOC 2 & ISO 27001

**Classification:** Internal · **Related:** KI-10 · **Prerequisite for:** KI-11 (MiCA)
**Purpose:** Map KI's existing technical controls to the frameworks auditors
expect, so KI-11 (crypto-asset compliance) and external audits have a trace.

## SOC 2 (AICPA TSC) — Common Criteria (CC)

| CC | Control area | KI evidence |
|----|--------------|-------------|
| CC1 | Control environment | `isms-policy.md`, role model |
| CC2 | Comm/info | AGENTS.md governance; Linear→OneDev issue tracking |
| CC3 | Risk assessment | `risk-register.md` |
| CC4 | Monitoring | CI gates, `verify-platform.sh`, event-bus durability |
| CC5 | Control activities | Gateway authz, SOPS, migration checksums |
| CC6 | Logical access | `agent-access.md`, least-privilege, resolver-gated EAS |
| CC7 | Vulnerability mgmt | pip-audit/semgrep/slither in CI |
| CC8 | Change mgmt | branch→PR→CI→merge; no direct main |
| CC9 | Risk mitigation | `risk-mitigation.md`; incident spec |

## ISO 27001:2022 — Annex A (selected)

| Clause | Control | KI evidence |
|--------|---------|-------------|
| A.5.1 | Policies | `isms-policy.md` |
| A.5.2 | Roles/responsibilities | role model docs |
| A.6.1 | Screening | Core Team approval gate |
| A.7.1 | Physical security | `cerberus` hardening; co-host isolation |
| A.8.1 | User access | gateway auth, SOPS, RBAC |
| A.8.2 | Privileged access | host key host-only; agent no prod secrets |
| A.8.3 | Info access restriction | Directus roles; opt-in public routes |
| A.8.4 | Source code | private repo; CI-only secrets |
| A.8.5 | Secure config | compose port isolation; namespace pin |
| A.8.6 | Boundary protection | cloudflared tunnel; app-level auth |
| A.8.7 | Data masking | PII residency (data-handling.md) |
| A.8.8 | Mgmt of secrets | SOPS+age; `check-tracked-secrets.sh` |
| A.8.9 | Data backup | nightly verified backup |
| A.8.10 | Logging | scheduler/event durability tests |
| A.8.11 | Ops resilience | backup + restore rehearsal |
| A.8.12 | Data leakage | resolver-gated attestation; no raw PII sync |
| A.8.13 | Info backup | same as A.8.9 |
| A.8.14 | Redundancy | (KI-8 planned — edge replicas) |
| A.8.15 | Logging/monitoring | CI + durability |
| A.8.16 | Monitoring activities | event bus |
| A.8.17 | Clock sync | container NTP |
| A.8.18 | Use of privileged util | sudo audit |

## Coverage gaps (to close in v1.1)

- A.5.x formal approval recorded (this pack adds it)
- A.8.14 redundancy → depends on KI-8 (noted, not blocking)
- A.6.2/6.3/6.4 (termination, legal/regulatory) → HR process, out of repo
  scope; flagged for Core Team

## Crypto-asset controls (KI-11 handoff)

- `KokonutCreditToken`: role-controlled issuance/retirement, supply accounting,
  pausing, non-transferable → maps to CC6 + A.8.1/8.2
- Guild points non-transferable → reduces MiCA market-risk profile
- Escrow/settlement balances → A.8.1 access restriction
