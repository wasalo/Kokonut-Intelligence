# EBF Scorecard Guide

Kokonut EBF scorecards evaluate syntropic farms across seven ecological benefit pillars: air quality, water management, soil health, biodiversity, carbon sequestration, equity and community, and implementation quality.

## Status

EBF scorecards use the canonical Kokonut lifecycle:

- `draft`
- `submitted`
- `verified`
- `published`
- `rejected`

Do not use lifecycle `status` for calibration phases, payment state, attestation state, or dashboard readiness. Use calibration fields, evidence maturity, and metadata for those concerns.

## Evidence Gates

Public EBF scorecards require:

- `ebf_scorecard.status = 'published'`
- `ebf_scorecard.evidence_maturity_level >= 4`
- `ebf_scorecard.public_claim_allowed = TRUE`
- Every public pillar score has at least one `ebf_score_evidence` link
- Every public pillar score has `evidence_maturity_level >= 4`
- Public carbon pillar scores use `evidence_maturity_level = 6`
- The location has a verified or published `farm_registry_record`

Public views intentionally hide reviewer notes, internal calibration detail, and private source evidence.

## Calibration

Rubric calibration should be performed by third-party reviewers. If the Kokonut team performs calibration, a report URL or report hash is required before verification or publication.

Pilot farms may calibrate semi-annually. Network farms should calibrate annually unless a governed process records a different cadence.

## CIDS Mapping

EBF score outputs map to existing CIDS Essential Tier classes:

- `metric_definition` becomes `cids:Indicator`
- verified `metric_value` becomes `cids:IndicatorReport`
- `impact_claim` remains `cids:ImpactReport`

No new CIDS class is introduced for EBF scorecards. The exporter adds Kokonut metadata such as `kokonut:framework = ebf` and `kokonut:ebfPillar` for EBF score metric outputs.

## Portfolio Use

Portfolio views use messy roll-ups by pillar, confidence, and evidence maturity. They are not farm rankings.

Use:

```bash
python3 -m services.analytics --ebf-portfolio-summary
```

## CSV Templates

Templates are available at:

- `exports/templates/ebf_scorecard_template.csv`
- `exports/templates/ebf_evidence_template.csv`

The spreadsheet bridge validates EBF CSV files but does not publish scorecards.

## Report Snapshots

Generate a public-safe scorecard report with:

```bash
python3 -m services.export.report_generator --type ebf_scorecard --location-id UUID
```

The report uses `v_public_ebf_scorecard_summary` and `v_public_ebf_scorecard`, so it only includes publication-ready records.

## Agent Boundaries

Agents may draft scorecards, summarize evidence gaps, and prepare calibration memos. Agents may not verify scores, publish scorecards, raise evidence maturity to public levels, certify carbon claims, or expose private stakeholder feedback.
