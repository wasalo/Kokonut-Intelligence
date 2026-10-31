# Control Mapping — SOC 2 & ISO 27001

**Classification:** Internal · **Related:** KI-10 · **Prerequisite for:** KI-11 (MiCA)
**Purpose:** Map KI's existing technical controls to the frameworks auditors
expect, so KI-11 (crypto-asset compliance) and external audits have a trace.

## SOC 2 (AICPA TSC) — Common Criteria (CC)

| CC | Control area | KI evidence |
|----|--------------|-------------|
| CC1 | Control environment | `isms-policy.md`, role model |
| CC2 | Comm/info | AGENTS.md governance; GitHub pull requests and review |
| CC3 | Risk assessment | `risk-register.md` |
| CC4 | Monitoring | CI gates, `verify-platform.sh`, event-bus durability |
| CC5 | Control activities | Gateway authz, SOPS, migration checksums |
| CC6 | Logical access | `agent-access.md`, least-privilege, resolver-gated EAS |
| CC7 | Vulnerability mgmt | pip-audit/semgrep/slither in CI |
| CC8 | Change mgmt | branch→PR→CI→merge; no direct main |
| CC9 | Risk mitigation | `risk-mitigation.md`; incident spec |

## ISO 27001:2022 — Annex A (selected)

This table is an evidence map, not an audit result or proof that a control is
operating in a deployed environment. Entries involving hosting, ingress,
backups, time synchronization, and privileged access require current owner and
runtime evidence before they are reported as implemented controls.

| Clause | Control | KI evidence |
|--------|---------|-------------|
| A.5.1 | Policies | `isms-policy.md` |
| A.5.2 | Roles/responsibilities | role model docs |
| A.6.1 | Screening | Core Team approval gate |
| A.7.1 | Physical security | Current host hardening and co-host isolation evidence required; the historical `cerberus` reference is not verified here |
| A.8.1 | User access | gateway auth, SOPS, RBAC |
| A.8.2 | Privileged access | SOPS+age key custody and CI secret isolation; deployment-specific evidence required |
| A.8.3 | Info access restriction | Gateway route policies, tenant/operator grants, database privileges; Directus roles and hooks where the adapter is enabled |
| A.8.4 | Source code | GitHub repository governance and branch protections; repository is open source, so source confidentiality is not an assumed control |
| A.8.5 | Secure config | Compose network/port isolation and pinned images; verify the selected profile |
| A.8.6 | Boundary protection | Active ingress configuration and application auth; verify any Cloudflare Tunnel deployment separately |
| A.8.7 | Data masking | Public-safe projections and access policy; confirm masking/residency against data-handling policy |
| A.8.8 | Mgmt of secrets | SOPS+age; `check-tracked-secrets.sh` |
| A.8.9 | Data backup | Active backup configuration, retention policy, and restore evidence required |
| A.8.10 | Logging | scheduler/event durability tests |
| A.8.11 | Ops resilience | backup + restore rehearsal |
| A.8.12 | Data leakage | resolver-gated attestation; no raw PII sync |
| A.8.13 | Info backup | Active backup configuration, retention policy, and restore evidence required |
| A.8.14 | Redundancy | (KI-8 planned — edge replicas) |
| A.8.15 | Logging/monitoring | CI + durability |
| A.8.16 | Monitoring activities | event bus |
| A.8.17 | Clock sync | Host time-synchronization evidence required; containers use host time and no container NTP control is claimed |
| A.8.18 | Use of privileged util | Host privilege and audit evidence required for each deployment |

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
