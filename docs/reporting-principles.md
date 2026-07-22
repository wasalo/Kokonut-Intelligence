# Reporting Principles

Kokonut Green Paper reports should be useful to partners without overstating evidence quality, hiding adverse signals, or exposing private stakeholder evidence. PostgreSQL/Directus remains the canonical governance, consent, lifecycle, and evidence layer. Reports, dashboards, and CIDS exports are derived presentation or compatibility layers.

## Public-Interest Defaults

- Use governed records and public-safe summaries, not raw private evidence.
- Treat stakeholder feedback as private by default.
- Pair positive claims with limitations, evidence gaps, uncertainty notes, and relevant negative findings.
- Distinguish observed records, reviewed claims, modeled outputs, forecasts, scenario analysis, attestations, and external verification.
- Do not present a report as a guarantee of future performance, causation, certification, regulatory compliance, credit issuance, solvency, funding, or commercial scale.
- Keep public carbon-balance claims separate from carbon-credit issuance.

## Object-Specific Publication Gates

There is no single maturity threshold for every public output. Evidence maturity is distinct from lifecycle status, consent, attestation, registry eligibility, and external verification.

| Object/output | Effective public gate |
|---|---|
| Ordinary `impact_claim` | `public_claim = TRUE`, `status = 'published'`, maturity >= 4, registry-backed location |
| Public carbon claim | Published, maturity 6, carbon category/type, external verifier, methodology reference |
| Stakeholder feedback | Explicit consent, public-safe scope, published status, `is_public = TRUE`, non-empty `public_summary`; no universal maturity >= 4 rule |
| Public metric summary | Active definition, verified `metric_value`, active location, verified/published farm registry |
| Attestation summary | Applicable lifecycle, Celo chain, expiry/revocation, and registry conditions |
| Report snapshot | Governed lifecycle and applicable source-specific gates; no universal base-schema maturity gate |
| CIDS export | Verified/published source records with maturity labels where available; not a universal maturity gate |

Public carbon claims additionally require `claim_category = 'carbon'` and `claim_type = 'third_party_verified_claim'` where those fields apply. EAS attestation metadata does not replace external verification or methodology requirements.

## Stakeholder Privacy

Public feedback requires all applicable conditions:

- `consent_given = TRUE`;
- a public-safe `consent_scope`;
- `status = 'published'`;
- `is_public = TRUE`;
- a non-empty `public_summary`.

Public reports may include consented summaries and aggregate private/no-consent counts. They must not expose raw private feedback, private identities, household-level details, private evidence, or unconsented quotations. A public summary is not permission to publish the underlying raw record.

Affected-community voice should preserve meaningful concerns and minority views while remaining consented, public-safe, and non-identifying.

## Public-Interest Context

`services/export/report_generator.py` attaches a `public_interest` section to UUID-scoped report data when available. It can include public feedback, public claims, evidence gaps, stakeholder aggregates, cultural context, wellbeing metrics, participatory actions, financial sustainability, risk mitigation, forecast performance, backcast health, assumption challenges, Delphi dissent, CRISP risk, and prediction calibration.

When a snapshot is stored, the generator writes:

| `report_snapshot` field | Purpose |
|---|---|
| `public_interest_summary` | Joined limitations for non-technical readers |
| `uncertainty_notes` | Data, sample-size, methodology, and forecast caveats |
| `negative_findings` | Structured gaps, adverse signals, and review prompts |
| `affected_community_voice` | Public-safe stakeholder summaries |

`build_negative_findings()` can report:

- claims below public thresholds;
- carbon publication gaps;
- missing CIDs, hashes, or attestation references;
- verified forecast overprediction;
- failed or insufficient prediction calibration;
- blocked or overdue backcast milestones;
- unresolved assumption challenges;
- Delphi non-consensus;
- elevated CRISP risk;
- limited CRISP evidence confidence.

These are review signals, not automatic causal conclusions. If no findings are detected, the report still states that this does not prove adverse outcomes or evidence gaps are absent.

## Report Snapshot Lifecycle

`report_snapshot` uses the governed lifecycle:

```text
draft -> submitted -> verified -> published
draft -> rejected -> draft
```

`store_snapshot()` starts every stored report as:

```text
status = 'draft'
frozen = FALSE
frozen_at = NULL
```

Storage does not verify, freeze, or publish a report. The snapshot hash is a reproducibility/integrity value, not an approval or evidence-maturity result. Hash verification recomputes PASS/FAIL but does not update status, freeze the snapshot, or create a verification record.

The hash covers the report plus attached public-interest context. Regeneration can change the hash when fields such as `generated_at` change. Snapshot storage does not generate a report file and has no generic deduplication or idempotency key.

## Generation And Scope

```bash
# Generate one report
python3 -m services.export.report_generator \
  --type environmental --location-id LOCATION_UUID

# Generate all registered report types for a supported scope
python3 -m services.export.report_generator \
  --auto --location-id LOCATION_UUID

# List snapshots or verify a UUID/exact hash
python3 -m services.export.report_generator --list
python3 -m services.export.report_generator --verify SNAPSHOT_UUID_OR_EXACT_HASH
```

Supported flags are `--type`, repeatable `--location-id`, `--all`, `--period-start`, `--period-end`, `--list`, `--verify`, and `--auto`.

`--auto` attempts all registered report generators independently. Successful reports may persist when other generators fail, the command exits nonzero if any generator fails, and there is no all-or-nothing transaction across the report set.

`--all` passes the literal scope `all`; only network-aware generators interpret it as a network scope. Many location-specific generators require a UUID and may fail for `all` or multiple location IDs. Period arguments are forwarded to generators, but there is no universal report-level date-filtering contract.

## Report-Specific Limitations

Individual generators include domain-specific `limitations`, including:

- forecasts, financial projections, scaling economics, and payback values are estimates, not guaranteed performance, ROI, or funding;
- capital-provider utility scenarios are not offers of securities or guaranteed returns;
- ecological models and simulations are estimates, not guaranteed outcomes;
- bio-factory yields are pilot evidence, not commercial production guarantees;
- quality tests are advisory, not certification or regulatory compliance;
- stress tests do not guarantee solvency or capital availability;
- replication readiness is conditional evidence, not an unlimited-scaling claim;
- adaptive stewardship reviews are management evidence, not proof that risks are eliminated;
- participatory signals are advisory unless their binding configuration and human approval state otherwise;
- CRISP and other scores are modeled assessments that require confidence and evidence context.

Keep the report’s `limitations` array visible when sharing or publishing the report.

## Dashboard And CIDS Review

Use these dashboards before publishing Green Paper materials:

- `dashboards/metabase/sql/20_evidence_gap_dashboard.sql` for claims needing stronger evidence;
- `dashboards/metabase/sql/21_stakeholder_feedback_dashboard.sql` for consent, maturity, sentiment, and public-summary review.

Treat missing evidence links, public claims below applicable thresholds, carbon gaps, unresolved privacy issues, and insufficient calibration as review items rather than public proof.

CIDS export is a compatibility layer. It emits maturity labels and mapped public-safe evidence, but it does not create or publish canonical records. Source lifecycle, consent, registry, and evidence gates remain authoritative in PostgreSQL/Directus.

## Agent And Human Review Boundaries

Agents may prepare report context, summaries, or drafts, but cannot verify or publish governed report snapshots. Human reviewers must confirm source lineage, evidence maturity, limitations, negative findings, affected-community voice, privacy gates, and claim-specific publication requirements before release.

## References And Verification

- Report generator: `services/export/report_generator.py`
- Snapshot schema: `schemas/postgres/007_modeled_outputs.sql`
- Public-interest fields and evidence foundations: `schemas/postgres/029_impact_accountability_foundation.sql`
- Evidence model and object-specific gates: `docs/evidence-maturity.md`
- Public disclaimer: `docs/public-report-disclaimer.md`
- Export operations: `docs/export-guide.md`
- Common publication checklist: `docs/common-foundations-checklist.md`
- Report governance tests: `tests/test_report_governance.py`
- Common foundations tests: `tests/test_common_foundations.py`

This document is a reporting review aid, not a substitute for the source record’s lifecycle, evidence, consent, registry, external-verification, or publication controls.
