# Compliance Baseline Re-Scan — 2026-08

**Scope:** 15 compliance-relevant areas on `main` at `c92e2ff` (v1.0.0).
**Purpose:** Confirm the readiness percentages from the KI-10 assessment
(performed weeks earlier) before authoring the ISMS pack.

## Scan results

| # | Area | Evidence found | Readiness |
|---|------|----------------|-----------|
| 1 | Secrets management | `.env.sops` + `.sops.yaml` + `scripts/load-secrets.sh`; SOPS+age host-key re-wrap in deploy | ✅ Strong |
| 2 | Authn/Authz (gateway) | `services/gateway`, `tests/test_gateway_auth.py` (12 test fns) | ✅ Strong |
| 3 | Audit log / event durability | `test_event_bus_durability.py`, `test_scheduler_durability.py` | ✅ Strong |
| 4 | Migration integrity | Ordered+checksummed migrations; `test_migration.py` | ✅ Strong |
| 5 | Backup / DR | `deploy/scripts/staging-backup.sh`, nightly 03:30, verified | ✅ Strong |
| 6 | Data lifecycle governance | `draft→submitted→verified→published` in AGENTS.md | ✅ Strong |
| 7 | Carbon credit custody | `test_carbon_credits.py`, atomic retirement + human confirm | ✅ Strong |
| 8 | Attestation integrity (EAS) | `test_attestation.py`, `contracts/src/KokonutCreditToken.sol`, Resolver-gated | ✅ Strong |
| 9 | Policy docs | `docs/kgp-security-model.md`, `workflow-emergency-incident.md` exist; **no `docs/compliance/` dir** | ⚠️ Partial |
| 10 | Risk register / ISMS | `docs/crisp-risk-scoring.md`, `risk-mitigation.md` exist (advisory) — no formal ISMS | ⚠️ Partial |
| 11 | Access control matrix | Role/circle pilot docs + `agent-access.md` + workflow-governance-role* | ⚠️ Partial |
| 12 | CI/CD supply chain | `pip-audit`, `semgrep`, `slither` in `.onedev-buildspec.yml` | ✅ Strong |
| 13 | Incident response | `docs/workflow-emergency-incident.md` (spec + invariants) | ⚠️ Partial |
| 14 | Data residency / retention | 17 references in AGENTS.md/docs; no consolidated policy | ⚠️ Partial |
| 15 | Vendor / third-party | Referenced in AGENTS.md governance; no register | ⚠️ Partial |

## Verdict

**Baseline confirmed — unchanged from original assessment:**
- SOC 2 Type I: **~70%** (strong technical controls, missing policy docs)
- ISO 27001:2022: **~55%** (good controls, missing ISMS documentation)
- Test suite: ~2,800 collectible on host; `test_migration.py` requires the
  SOPS age key (expected — runs in CI/staging, not locally)

## Gap summary (what this branch adds)

1. Formal ISMS policy doc (`isms-policy.md`)
2. Consolidated risk register (`risk-register.md`)
3. Access-control matrix (from existing role docs → `data-handling.md`)
4. Data residency + retention schedule (`data-handling.md`) — **prerequisite
   for KI-8**
5. Control mapping SOC2/ISO (`control-mapping.md`) — **prerequisite for KI-11**
6. Evidence collection wired into `scripts/verify-platform.sh`

No new infrastructure. No schema changes.
