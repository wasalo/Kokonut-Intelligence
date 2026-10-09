# Risk Register

**Source:** Consolidated from `docs/crisp-risk-scoring.md`,
`docs/risk-mitigation.md`, and the KI-10 compliance re-scan (2026-08).
**Classification:** Internal · **Related:** KI-10

Risks are scored on Likelihood (1–5) × Impact (1–5) = Score (1–25).
Score ≥ 12 = High; 6–11 = Medium; <6 = Low.

| ID | Risk | Domain | L | I | Score | Treatment | Owner |
|----|------|--------|---|---|-------|----------|-------|
| R-01 | Secret leakage via mis-committed key | Crypto | 2 | 5 | 10 | SOPS+age; `check-tracked-secrets.sh`; rotate+scrub on leak | Core |
| R-02 | Unverified metric published as fact | Data | 2 | 4 | 8 | Governed lifecycle; human `--verify-value` | Human |
| R-03 | Migration drift / unapplied change | Integrity | 1 | 4 | 4 | Ordered+checksummed; drift detection fails CI | Agent |
| R-04 | Staging data loss | Availability | 1 | 4 | 4 | Nightly verified backup; restore rehearsal | Ops |
| R-05 | Unauthorized gateway route | Access | 1 | 5 | 5 | Opt-in public; authz tests per route | Agent |
| R-06 | Credit double-spend / bad retirement | Crypto | 1 | 5 | 5 | Atomic custody; human confirm before mutation | Human |
| R-07 | Missing ISMS documentation | Compliance | 3 | 3 | 9 | This register + `isms-policy.md` | Core |
| R-08 | Data residency breach (cross-border) | Legal | 2 | 4 | 8 | `data-handling.md` residency notice (prereq KI-8) | Core |
| R-09 | MiCA non-compliance on issuance | Legal | 2 | 4 | 8 | Control mapping (prereq KI-11) | Core |
| R-10 | Supply-chain dependency compromise | CI | 1 | 4 | 4 | pip-audit/semgrep/slither in CI | Agent |

## Treatment strategy

- **Mitigate (most):** documented controls above.
- **Accept (R-03, R-04):** low likelihood, detected+recoverable.
- **Transfer:** none currently; production insurance evaluated under KI-9.

## Review cadence

Quarterly, or on incident. Scores recomputed after each v1.1 compliance
milestone; target to move all High→Medium by v1.1 close.
