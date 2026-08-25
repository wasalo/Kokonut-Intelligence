# Kokonut Intelligence — Compliance Pack

This directory consolidates the evidence and policy artifacts for operational
and data compliance (KI-10). It supports SOC 2 Type I/II and ISO 27001:2022
readiness, and feeds downstream work:

- **KI-11 (MiCA)** — consumes the crypto-asset control mapping here
- **KI-8 (Distributed Replicas)** — consumes the data-residency + retention
  policy here before sharding by `location_id`

## Structure

| File | Purpose |
|------|---------|
| `baseline-rescan-2026-08.md` | Re-scan of the 15 compliance areas on `v1.0.0` (main @ c92e2ff) — confirms the % baseline |
| `control-mapping.md` | Maps existing technical controls → SOC 2 CC / ISO 27001 A.5–A.8 |
| `isms-policy.md` | Information security policy (scope, objectives, roles) |
| `risk-register.md` | Consolidated risk register (from crisp-risk-scoring + risk-mitigation) |
| `data-handling.md` | Data classification, retention schedule, residency notice |
| `evidence/` | Machine-readable evidence emitted by `scripts/verify-platform.sh` and CI |

## Status

- Baseline (2026-08): SOC 2 Type I ~70%, ISO 27001 ~55% — strong technical
  controls, missing ISMS documentation. Target for v1.1: +20pts on both via
  the docs above (no new infrastructure).
- SOC 2 Type II observation window (6–12 mo) is an explicit **out-of-scope
  follow-up** — noted in KI-10, not blockable in this release.
