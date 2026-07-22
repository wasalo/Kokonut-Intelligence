# Reviewer Guide

Reviewers protect public trust by checking lifecycle state, evidence maturity, consent, and claim scope before publication.

## Review Checklist

- Confirm records use `draft`, `submitted`, `verified`, `published`, or `rejected` correctly.
- Confirm source lineage fields are populated where the owning schema requires them; do not assume every record has the same lineage contract.
- Confirm each public output satisfies its object-specific lifecycle, consent, registry, evidence, and public-safe gates; there is no universal maturity threshold for every view.
- Confirm private stakeholder feedback is not leaked into public summaries.
- Confirm public claims include limitations and evidence maturity.
- Confirm computed `metric_value` records remain drafts until a named human explicitly verifies them; computation is not verification.
- Confirm forecast runs are `submitted` projections and have not bypassed human verification or publication review.
- Confirm derived outputs such as reports, CIDS, RDF, dashboards, and metadata do not become a second canonical governance layer.

## Carbon Claims

Public carbon claims require:

- `public_claim = TRUE` where the claim object has that field
- `claim_category = 'carbon'`
- `claim_type = 'third_party_verified_claim'`
- `evidence_maturity = 6`
- non-empty `external_verifier`
- non-empty `methodology_ref`
- `status = 'published'`
- a verified or published farm registry record where the public view requires one

These are the carbon-specific gates in addition to the applicable ordinary public-claim gates. Level 5 attestations prove a record was attested; they do not equal external verification.

Keep carbon-balance evidence separate from carbon-credit issuance, retirement, and certificate generation. Do not describe platform ledger records as externally registered or certified without matching registry evidence and identifiers.

## Dashboards

Use these dashboards before Green Paper publication:

- `dashboards/metabase/20_evidence_gap_dashboard.json`
- `dashboards/metabase/21_stakeholder_feedback_dashboard.json`
- `dashboards/metabase/22_ebf_scorecard.json`
- the EBF evidence-gap and calibration-history dashboards under `dashboards/metabase/sql/23_*.sql` and `dashboards/metabase/sql/24_*.sql`

Internal evidence-gap and calibration dashboards are not public-safe by default.

## Agent Outputs

Agent-created summaries, evidence-gap reports, calibration memos, and tasks must remain within the collection-specific draft/submitted/rejected boundaries. Agents cannot verify or publish governed records, raise EBF maturity above the permitted safety limit, or treat a supplied accountability field as human approval. Reviewers may use agent drafts as inputs, but final verification, publication, and high-risk actions remain human governance decisions.

## Threats, Backcasts, And Delphi

- Trace threat severity, probability, warning flags, signals, and cross-impact claims to dated sources. Separate observations from modeled narratives and document uncertainty.
- For forecast questions, confirm the event definition, resolution criteria and source, open/close/resolution dates, immutable forecast submissions, and explicit invalid/cancelled handling. A forecast is not scored as a resolved outcome until it has valid resolution evidence.
- For backcasts, confirm the future state, principles, current metrics, gaps, milestones, dependencies, and challenged assumptions are internally consistent. Treat automated alignment and path scores as advisory, especially where manual overrides exist.
- Resolve assumption challenges only with a recorded human decision and rationale. Confirm milestones do not imply commitments that lack capital, partner, governance, or operational approval.
- For Delphi studies, check panel eligibility and weighting, item scale definitions, participation coverage, IQR/CV and stability evidence, diversity diagnostics, minority-report status, and the configured stopping rule. Preserve pseudonymity in summaries.
- A facilitator agent may draft a Delphi recommendation, but approval must identify a human approver UUID. Consensus is structured input, not automatic policy or publication authority.
- Treat `check-stopping` as advisory: it does not close a study, and a time-limit result is not the same as consensus. Disclose that post-hoc expert calibration weights do not automatically change live panel weights.
- Confirm path scores distinguish unknown evidence from measured midpoint performance. An incomplete comparison or tied result must not nominate a winner.
- Review one submitted premortem for every candidate path. Verify failure modes, disconfirming evidence, uncontrollable dependencies, warning signals, mitigations, residual harms, and affected stakeholders.
- Treat a nominated path as advisory; premortem verification confirms review quality, not authorization to execute. Minority views and dissent must remain visible in anonymized, public-safe form where publication is permitted.

## Bias-Resilient Review

- Compare success and failure probabilities derived from the same underlying estimate.
- Ask which assumptions depend on perceived control and which depend on weather, markets, policy, partners, or community consent.
- Require disconfirming evidence and a comparable outside-view case, not only evidence supporting the desired outcome.
- For forecasts, define signed error explicitly and show repeated overprediction beside aggregate accuracy.
- Treat reference-class and outside-view comparisons as assumption-review evidence, not guarantees of forecast accuracy.
- For backcasts, distinguish blocked milestones from overdue milestones and confirm whether target dates remain authoritative.
- For Delphi, disclose non-consensus and anonymized minority views rather than presenting convergence as correctness.
- For CRISP, state that higher scores mean higher risk and separate modeled risk severity from evidence confidence.
- Never interpret absence of records or configured findings as evidence that harms, failures, or evidence gaps are absent.

## Credit Records

- Confirm a batch was human-verified before issuance and that the issuer was authorized for its credit class.
- Reconcile issued, tradable, escrowed, reserved, retired, and cancelled quantities; confirm non-negative balances and review custody/bridge history for double counting.
- Confirm retirement reserves quantity before final mutation, uses an idempotency key, and is reviewed by a human other than the requester. Review the reviewer UUID, review date, decision, notes, and confirmation/cancellation timestamps.
- Treat Kokonut issuance and retirement as governed platform ledger events. Do not describe them as externally registered, certified, or recognized without matching external registry evidence and identifiers.

## EBF Scorecard Review

- Confirm the scorecard is published, has `public_claim_allowed = TRUE`, and meets the scorecard maturity gate.
- Confirm the scorecard uses all seven EBF pillars.
- Confirm each public-enabled pillar score has at least one `ebf_score_evidence` link and satisfies the applicable maturity gate.
- Confirm `v_public_ebf_scorecard` exposes only published, public-safe, registry-backed records.
- Confirm team calibration has the required report URL or hash before verification/publication; third-party calibration is preferred. Do not treat a scalar calculator or agent memo as human calibration.
- Confirm public carbon pillar scores use evidence maturity Level 6 and link to a published third-party-verified carbon claim with verifier and methodology.
- Confirm portfolio views use messy roll-ups and include caveats against farm ranking.
- Confirm trust graph public exports use `--public-safe` and include only public-safe nodes and edges; reviewer identities, private evidence, and internal calibration details must remain excluded.

## Report Snapshots

- Confirm stored snapshots begin as `status = 'draft'`, `frozen = FALSE`, and `frozen_at = NULL`.
- Treat the snapshot hash as an integrity/reproducibility value, not as verification, publication, or evidence maturity. Hash verification reports PASS/FAIL without changing lifecycle state or creating a review record.
- Review `public_interest_summary`, `uncertainty_notes`, `negative_findings`, `affected_community_voice`, and the report-specific `limitations` array before release.
- Expect `--auto` report generation to process generators independently: successful reports may persist when another generator fails, and a nonzero exit means the report set is incomplete rather than transactionally rolled back.
- Confirm negative findings are considered, including below-threshold claims, carbon gaps, missing evidence references, forecast overprediction, insufficient calibration, blocked or overdue milestones, unresolved assumption challenges, Delphi non-consensus, elevated CRISP risk, and limited evidence confidence.

## Public Stakeholder Evidence

- Require `consent_given = TRUE`, a public-safe consent scope, `status = 'published'`, `is_public = TRUE`, and a non-empty `public_summary` for public feedback.
- Permit aggregate counts of private or no-consent feedback where the report supports them, but never expose raw records, identities, household details, private evidence, or unconsented quotations.
- Preserve affected-community concerns and minority views without implying that a summary represents every affected person.

## References And Tests

- Evidence gates: `docs/evidence-maturity.md`
- Reporting behavior: `docs/reporting-principles.md`, `docs/public-report-disclaimer.md`, `docs/export-guide.md`
- Agent boundaries: `services/agents/safety.py`
- EBF gates and exports: `services/scoring/gates.py`, `services/scoring/export.py`, `services/scoring/trust_graph.py`
- Relevant tests: `tests/test_report_governance.py`, `tests/test_common_foundations.py`, `tests/test_ebf_gates.py`, `tests/test_ebf_public_views.py`, `tests/test_ebf_trust_graph.py`, `tests/test_delphi.py`, `tests/test_prediction_calibration.py`, and `tests/test_carbon_credits.py`
