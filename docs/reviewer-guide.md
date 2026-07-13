# Reviewer Guide

Reviewers protect public trust by checking lifecycle state, evidence maturity, consent, and claim scope before publication.

## Review Checklist

- Confirm records use `draft`, `submitted`, `verified`, `published`, or `rejected` correctly.
- Confirm source lineage fields are populated for evidence-bearing records.
- Confirm public views expose only verified/published and public-safe records.
- Confirm private stakeholder feedback is not leaked into public summaries.
- Confirm public claims include limitations and evidence maturity.
- Confirm computed `metric_value` records remain drafts until a named human explicitly verifies them; computation is not verification.
- Confirm forecast runs are `submitted` projections and have not bypassed human verification or publication review.

## Carbon Claims

Public carbon claims require:

- `claim_category = 'carbon'`
- `claim_type = 'third_party_verified_claim'`
- `evidence_maturity = 6`
- non-empty `external_verifier`
- non-empty `methodology_ref`
- `status = 'published'`

Level 5 attestations prove a record was attested; they do not equal external verification.

## Dashboards

Use these dashboards before Green Paper publication:

- `dashboards/metabase/20_evidence_gap_dashboard.json`
- `dashboards/metabase/21_stakeholder_feedback_dashboard.json`
- `dashboards/metabase/22_ebf_scorecard.json`

## Agent Outputs

Agent-created summaries and tasks must not be verified or published by the agent. Reviewers may use agent drafts as inputs, but final publication remains a human governance decision.

## Threats, Backcasts, And Delphi

- Trace threat severity, probability, warning flags, signals, and cross-impact claims to dated sources. Separate observations from modeled narratives and document uncertainty.
- For backcasts, confirm the future state, principles, current metrics, gaps, milestones, dependencies, and challenged assumptions are internally consistent. Treat automated alignment and path scores as advisory, especially where manual overrides exist.
- Resolve assumption challenges only with a recorded human decision and rationale. Confirm milestones do not imply commitments that lack capital, partner, governance, or operational approval.
- For Delphi studies, check panel eligibility and weighting, item scale definitions, participation coverage, IQR/CV and stability evidence, and the configured stopping rule. Preserve pseudonymity in summaries.
- A facilitator agent may draft a Delphi recommendation, but approval must identify a human approver UUID. Consensus is structured input, not automatic policy or publication authority.

## Credit Records

- Confirm a batch was human-verified before issuance and that the issuer was authorized for its credit class.
- Reconcile issued, tradable, escrowed, retired, and cancelled quantities and review custody/bridge history for double counting.
- Treat Kokonut issuance and retirement as governed platform ledger events. Do not describe them as externally registered, certified, or recognized without matching external registry evidence and identifiers.

## EBF Scorecard Review

- Confirm the scorecard uses all seven EBF pillars.
- Confirm each public pillar score has at least one `ebf_score_evidence` link.
- Confirm `v_public_ebf_scorecard` exposes only published, public-safe, registry-backed records.
- Confirm calibration reports exist for team-led calibration before verification or publication.
- Confirm public carbon pillar scores use evidence maturity Level 6.
- Confirm portfolio views use messy roll-ups and include caveats against farm ranking.
- Confirm trust graph public exports include only public-safe nodes and edges.
