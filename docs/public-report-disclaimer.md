# Public Report Disclaimer

Kokonut public reports are governed evidence summaries and decision-support outputs. They are not guarantees of future performance, proof of causation, automatic credit issuance, certification, regulatory compliance, solvency, funding, or commercial scale.

## Standard Disclaimer

Reports may include verified records, public stakeholder summaries, modeled outputs, forecasts, scenario analysis, risk assessments, and externally reviewed claims. These source types have different evidentiary meanings and must not be treated as interchangeable.

Each claim should be interpreted with:

- its evidence maturity level, where the source object provides one;
- lifecycle status and review state;
- methodology and source-record references;
- reviewer and external-verifier context;
- uncertainty notes and known limitations;
- negative findings and contradictory evidence;
- affected-community voice where it is consented and public-safe.

Modeled or forecast values describe assumptions and scenarios. Historical evaluation, attestation metadata, or human review does not turn a projection into a guarantee of future results.

## Report Snapshot Governance

`report_snapshot` is a governed record with the standard lifecycle:

```text
draft -> submitted -> verified -> published
draft -> rejected -> draft
```

When `services/export/report_generator.py` stores a snapshot, it starts as:

```text
status = 'draft'
frozen = FALSE
frozen_at = NULL
```

Snapshot storage does not verify, freeze, or publish a report. A snapshot hash is a reproducibility and integrity value; it is not an approval or evidence-maturity result. Hash verification recomputes and reports PASS/FAIL but does not change snapshot status, freeze the snapshot, or create a verification record.

The hash covers the generated report data together with attached public-interest context. Regenerating a report can produce a different hash when generated timestamps or context change.

Report snapshots may populate:

- `public_interest_summary`;
- `uncertainty_notes`;
- `negative_findings`;
- `affected_community_voice`.

`public_interest_summary` is derived from detected limitations; it is not a publication approval. Network-level reports may not have location-scoped public-interest context when no UUID location is available.

## Balanced Public-Interest Context

The report generator uses governed and public-safe views to attach context. Its negative-findings pass may identify:

- public claims below evidence thresholds;
- carbon publication and verification gaps;
- missing CIDs, hashes, or attestation references;
- verified forecast overprediction;
- failed or insufficient prediction calibration;
- blocked or overdue backcast milestones;
- unresolved assumption challenges;
- Delphi non-consensus;
- elevated CRISP risk;
- limited CRISP evidence confidence.

These findings are review signals, not automatic causal conclusions. A report with no detected findings must still state that absence of a detected finding does not prove that adverse outcomes or evidence gaps are absent.

Positive claims should be presented alongside relevant limitations, uncertainty, evidence gaps, and adverse signals rather than as a selective success narrative.

## Stakeholder Privacy

Stakeholder feedback is private by default. Public reports may include feedback only when all applicable public gates are satisfied:

- `consent_given = TRUE`;
- a public-safe `consent_scope`;
- `status = 'published'`;
- `is_public = TRUE`;
- a non-empty `public_summary`.

Public reports may include consented summaries and aggregate counts of private or no-consent feedback. They must not expose raw private feedback, private identities, household-level details, private evidence, or unconsented quotations. A public summary is not permission to publish the underlying raw record.

Affected-community voice must be consented and public-safe. It should preserve meaningful concerns and minority views without exposing identifying details or implying that a summary represents every affected person.

## Evidence Maturity And Publication Gates

Evidence maturity is not the same as lifecycle status, consent, attestation, or external verification. Raising maturity does not publish a record, and publishing does not establish external verification.

### Ordinary Impact Claims

Ordinary public `impact_claim` output requires:

- `public_claim = TRUE`;
- `status = 'published'`;
- evidence maturity at least 4;
- a registry-backed location for public views.

### Public Carbon Claims

Public carbon claims require all applicable ordinary gates plus:

- evidence maturity exactly 6;
- `claim_category = 'carbon'`;
- `claim_type = 'third_party_verified_claim'`;
- a non-empty external verifier;
- a non-empty methodology reference;
- published status.

Carbon-balance evidence is distinct from carbon credit issuance. EAS attestations provide verification metadata and provenance but do not replace independent external verification or methodology requirements.

### Carbon Credit Inventory

Published carbon credits require maturity 6, an external verifier, and a methodology reference. Public inventory additionally requires published status and a verified or published farm registry record. Credit issuance, custody, retirement, and certificate generation are separate governed workflows and do not by themselves establish recognition by Verra, Gold Standard, another registry, or a jurisdiction.

### EBF Scorecards

Public EBF scorecards require:

- a published scorecard;
- scorecard maturity at least 4;
- `public_claim_allowed = TRUE`;
- seven public pillar rows;
- public-enabled pillar scores;
- pillar maturity at least 4;
- evidence row or link for every public pillar;
- a verified or published farm registry record.

The carbon pillar has the stricter Level 6 carbon gate and requires a qualifying linked carbon claim. EBF portfolio views are confidence-labelled roll-ups and must not be presented as rankings of interchangeable farms.

### Metrics And Attestations

Public metric summaries require an active metric definition, a verified `metric_value`, an active location, and a verified or published farm registry record. Metric computation creates draft, unverified values; human verification is a separate action. Base metric tables do not use evidence maturity as a substitute for the metric verification flag.

Public attestation summaries require the applicable lifecycle, Celo-chain, revocation, expiry, and registry conditions. An attestation may support a maturity interpretation for a specific claim, but it does not automatically establish maturity 5 or 6 on every related object.

## Report-Type Limitations

Individual report generators include limitations appropriate to their domain. Examples include:

- forecasts, financial projections, scaling economics, and payback values are planning estimates, not guaranteed performance, ROI, or funding;
- capital-provider utility scenarios are not offers of securities or guaranteed returns;
- ecological models and simulations are estimates, not guaranteed outcomes;
- bio-factory yields are pilot evidence, not commercial production guarantees;
- quality tests are advisory and are not certification or regulatory compliance;
- stress tests do not guarantee solvency or capital availability;
- adaptive stewardship reviews are management evidence, not proof that risks are eliminated;
- participatory signals are advisory unless their decision-binding configuration and human approval say otherwise;
- CRISP ratings are modeled risk assessments and should be read with their confidence and evidence context;
- outside-view and reference-class comparisons are evidence for assumption review, not guarantees of forecast accuracy.

The applicable report’s `limitations` output and public-interest fields are part of the report context and should remain visible when the report is shared.

## Generation And Review Boundaries

The report generator can create one report or attempt all registered report types with `--auto`. Reports are handled independently: successful reports may be persisted even when other generators fail, and the command exits nonzero if one or more generators fail. There is no all-or-nothing transaction across the report set.

Before publication, reviewers should:

1. Confirm the report snapshot is in the appropriate governed lifecycle state.
2. Verify evidence maturity and object-specific publication gates.
3. Review limitations, uncertainty notes, negative findings, and affected-community voice.
4. Confirm private feedback and evidence are not exposed.
5. Check the Evidence Gap and Stakeholder Feedback dashboards.
6. Confirm carbon claims are separate from credit issuance and meet Level 6 external-verification requirements.
7. Recompute the snapshot hash when integrity verification is required.

Agents may prepare report context or drafts, but they cannot verify or publish governed report snapshots. Public release remains a human governance decision.

## References And Verification

- Report generator: `services/export/report_generator.py`
- Report snapshot schema: `schemas/postgres/007_modeled_outputs.sql`
- Public-interest fields and carbon constraints: `schemas/postgres/029_impact_accountability_foundation.sql`
- Evidence model and object-specific gates: `docs/evidence-maturity.md`
- Reporting principles: `docs/reporting-principles.md`
- Export and snapshot operations: `docs/export-guide.md`
- Common publication checklist: `docs/common-foundations-checklist.md`
- Report governance tests: `tests/test_report_governance.py`
- Common foundations tests: `tests/test_common_foundations.py`

This disclaimer is a review aid, not a substitute for the source record’s lifecycle, evidence, consent, registry, external-verification, or publication controls.
