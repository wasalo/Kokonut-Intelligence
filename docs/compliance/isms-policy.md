# Information Security Management System (ISMS) Policy

**Document owner:** Kokonut Core Team
**Classification:** Internal
**Related:** KI-10 · feeds KI-11 (MiCA), KI-8 (Replicas)
**Supersedes:** advisory notes in `docs/kgp-security-model.md`, `docs/crisp-risk-scoring.md`

## 1. Purpose & Scope

This policy establishes Kokonut Intelligence's (KI) information security
management system in support of SOC 2 Type I/II and ISO 27001:2022 readiness.
It applies to all KI infrastructure, code, and data: the canonical Postgres+
Directus+ClickHouse stack, the Gateway/GRPC services, CI (OneDev), and the
staging environment on `cerberus`.

Out of scope: Kokonut-Agentic-Marketplace smart-contract logic (separate
audit lineage) and production hosts not yet provisioned.

## 2. Information Security Objectives

1. Protect the confidentiality, integrity, and availability (CIA) of farm
   operational data and stakeholder records.
2. Maintain cryptographic control of all secrets; no plaintext secrets in git.
3. Ensure every state transition in governed data is human-verifiable
   (`draft → submitted → verified → published`).
4. Preserve auditability of credits, attestations, and control-plane events.

## 3. Roles & Responsibilities

| Role | Responsibility |
|------|----------------|
| Kokonut Core Team | Approves policy, owns risk acceptance |
| Syntropic Agent | Executes changes via branch→PR→CI; no direct main push |
| Farm Stewards | Data producers; source of truth for on-ground records |
| Human approver | Final sign-off on `published` state and prod deploys |

## 4. Control Domains (anchored to ISO 27001:2022)

- **A.5 Organizational** — this policy, risk register, vendor register
- **A.6 People** — role-based access, onboarding/offboarding
- **A.7 Physical** — `cerberus` VPS hardened; co-hosted services isolated
- **A.8 Technological** — gateway auth, SOPS, migration checksums, backup

## 5. Access Control

- Least-privilege by default; agents propose, humans approve.
- Secrets encrypted with SOPS+age; host key on `cerberus` only.
- CI never sees production secrets; deploy re-wraps to host key per run.

## 6. Cryptographic Controls

- Age (SOPS) for at-rest secrets; Celo EAS for attestations.
- KokonutResolver gates attester allow-list; multisig-owned.

## 7. Incident Management

Spec `emergency_incident` (see `docs/workflow-emergency-incident.md`):
invariants preserved, replay/disposal explicit. Severity → comms path defined.

## 8. Backup & Continuity

Nightly verified backup (03:30) of staging DB; 7-day retention on-host,
off-host copy per `deploy/production/backup-policy.md` at prod.

## 9. Compliance & Review

- This policy reviewed quarterly or on material change.
- Readiness tracked in `baseline-rescan-*.md`; target +20pts/framework in v1.1.
- SOC 2 Type II observation window is a post-v1.1 follow-up (noted, not
  blockable here).
