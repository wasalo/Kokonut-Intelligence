# EBF Scorecard Guide

Kokonut EBF scorecards evaluate syntropic farms across seven ecological benefit
pillars. A scorecard is a governed evidence summary for a location and period;
it is not an automatic certification, financial rating, or substitute for
third-party review.

## Seven Pillars

| Key | Pillar | Framework mapping |
|-----|--------|-------------------|
| `air_quality` | Air Quality | Environmental |
| `water_management` | Water Management | Environmental |
| `soil_health` | Soil Health | Environmental |
| `biodiversity` | Biodiversity | Environmental |
| `carbon_sequestration` | Carbon Sequestration | Sustainability |
| `equity_community` | Equity and Community | Social |
| `implementation_quality` | Implementation Quality | Sustainability |

The seed does not assign the existing `ebf_economic` framework dimension to an
EBF pillar.

## Score Scale And Rubric

Python calculators return scores from 0 to 10. The default labels are:

| Score | Label |
|-------|-------|
| 0–1 | `insufficient` |
| 2–3 | `emerging` |
| 4–5 | `developing` |
| 6–7 | `strong` |
| 8–10 | `leading` |

The SQL seed currently uses `generate_series(0, 9)`, creating 70 bands across
seven pillars. Score 10 is supported by Python but has no seeded database band.
Treat this as a rubric parity gap until the seed is corrected.

## Calculators

The functions in `services/scoring/calculators.py` normalize scalar inputs. They
do not query governed metric values, create scorecard rows, or publish results.

| Pillar | Input and normalization |
|--------|-------------------------|
| Air Quality | kg CO2e per acre, linear 0–5000 to 0–10 |
| Water Management | runoff reduction percentage, 0–100 to 0–10 |
| Soil Health | soil-carbon change percentage, -2–8 to 0–10 |
| Biodiversity | species richness index, 0–100 to 0–10 |
| Carbon Sequestration | total farm CO2e / area hectares, 0–20 to 0–10 |
| Equity and Community | Average of local-worker percentage and training-hours scores |
| Implementation Quality | SMART KPI completion percentage, 0–100 to 0–10 |

`compute_carbon_sequestration_score()` rejects non-positive farm area. Values
outside benchmark ranges are clamped by `normalize_linear()` and rounded by
`clamp_score()`.

`compute_equity_score_from_feedback()` is a separate database-backed heuristic.
It uses aggregate verified/published stakeholder feedback and does not return
raw feedback text.

## Confidence

`services/scoring/confidence.py` combines evidence quantity, maturity, and
public-safe coverage:

| Condition | Confidence |
|-----------|------------|
| No evidence or maturity ≤1 | `insufficient_evidence` |
| Maturity ≥5, at least 3 evidence rows, at least 2 public-safe | `high` |
| Maturity ≥4, at least 2 evidence rows, at least 1 public-safe | `moderate` |
| Other evidence combinations | `low` |

For a scorecard, any insufficient pillar produces insufficient confidence. All
high labels produce high confidence; high/moderate combinations produce
moderate confidence; other combinations produce low confidence.

## Lifecycle

EBF scorecards use the canonical lifecycle:

```text
draft → submitted → verified → published
                  ↘ rejected
```

| Status | Meaning |
|--------|---------|
| `draft` | Computed or imported but not submitted |
| `submitted` | Awaiting review |
| `verified` | Human-reviewed scorecard |
| `published` | Eligible for public-view evaluation |
| `rejected` | Returned for rework |

Do not use `status` for calibration phase, payment, attestation, dashboard
readiness, or evidence maturity. Those belong in calibration fields, metadata,
dedicated payment/attestation fields, and maturity columns.

## Database Model

Core schema: `schemas/postgres/032_ebf_scorecard.sql`.

| Table/view | Purpose |
|------------|---------|
| `ebf_pillar` | Pillar definitions and framework mapping |
| `ebf_rubric_band` | Score label and range for a pillar |
| `ebf_scorecard` | Location-period scorecard and lifecycle |
| `ebf_score` | One pillar score within a scorecard |
| `ebf_score_evidence` | Evidence link and evidence metadata |
| `v_public_ebf_scorecard` | Public-safe pillar score rows |
| `v_public_ebf_scorecard_summary` | Public-safe scorecard summary |
| `v_public_ebf_pillar_summary` | Pillar-level internal/public summary |

Operations schema: `schemas/postgres/033_ebf_p1_operations.sql`.

| Table/view | Purpose |
|------------|---------|
| `ebf_farm_metric_profile` | Location-to-metric/pillar profile |
| `ebf_calibration_session` | Calibration method, cadence, and report metadata |
| `ebf_calibration_decision` | Calibration decision and review state |
| `ebf_trust_graph_node` | Provenance node |
| `ebf_trust_graph_edge` | Typed provenance relationship |
| `ebf_improvement_recommendation` | Improvement recommendation |
| `v_ebf_evidence_gap_summary` | Internal evidence-gap summary |
| `v_ebf_calibration_history` | Internal calibration history |

Migration `042_fk_index_fixes.sql` adds EBF foreign-key indexes. No later
migration substantially changes these EBF definitions or public views.

## Evidence Gates

Public EBF scorecards require all applicable conditions:

The public scorecard views require all applicable conditions:

1. `ebf_scorecard.status = 'published'`.
2. `ebf_scorecard.evidence_maturity_level >= 4`.
3. `ebf_scorecard.public_claim_allowed = TRUE`.
4. Seven pillar score rows are present.
5. Each public pillar score is enabled for public output.
6. Each public pillar score has maturity at least 4.
7. Each public pillar has at least one evidence link.
8. The location has a `farm_registry_record` with status `verified` or
   `published`.

Public views intentionally exclude reviewer notes, internal calibration detail,
private source evidence, and non-public score rows.

### Carbon Pillar Gate

The carbon pillar requires stricter evidence:

- score evidence maturity exactly 6;
- an evidence link;
- a linked `impact_claim` with `claim_category = 'carbon'`;
- `claim_type = 'third_party_verified_claim'`;
- claim status `published`;
- external verifier;
- methodology reference.

In short, public carbon pillar scores use `evidence_maturity_level = 6` plus
the linked published third-party claim and verifier requirements above.

The public view checks the score's maturity field. It requires an evidence link,
but does not independently require the linked `ebf_score_evidence` row's own
`evidence_maturity_level` to be at least 4.

### Python Versus Database Gates

`services/scoring/gates.py` exposes reusable checks:

- `public_score_allowed(maturity, has_evidence_link)`
- `public_carbon_score_allowed(maturity, has_evidence_link)`
- `linked_carbon_claim_allowed(claim)`
- `score_publication_gate(...)`
- `scorecard_publication_gate(...)`

These helpers are advisory building blocks. `scorecard_publication_gate()` does
not reproduce every public-view join, including lifecycle status, public-claim
flag, registry status, seven-pillar completeness, and all carbon claim joins.
The database public views remain the authoritative public-safety boundary.

## Calibration

Calibration is separate from lifecycle status. Supported methods:

- `third_party`
- `team_with_report`
- `mixed_panel`

Supported frequencies:

- `annual`
- `semi_annual`
- `quarterly`
- `custom`

The schema stores calibration sessions and decisions, including report URL/hash
metadata. Pilot semi-annual and network annual cadence are recommendations, not
database-enforced rules. A report URL or hash is required for the applicable
team-calibration verification/publication path.

Calibration does not automatically verify scorecards, raise evidence maturity,
or create a third-party certification.

## Reports And Dashboards

### Public Scorecard Report

```bash
python3 -m services.export.report_generator \
  --type ebf_scorecard --location-id UUID
```

This report reads `v_public_ebf_scorecard_summary` and
public views. It is the only EBF-specific report generator currently registered;
there is no separate EBF portfolio report generator.

### Metabase Assets

- `dashboards/metabase/22_ebf_scorecard.json`
- `dashboards/metabase/24_portfolio_ebf.json`
- `dashboards/metabase/sql/22_ebf_scorecard.sql`
- `dashboards/metabase/sql/23_ebf_evidence_gap.sql`
- `dashboards/metabase/sql/24_ebf_calibration_history.sql`
- `dashboards/metabase/sql/25_ebf_portfolio_messy_rollup.sql`

The scorecard dashboard combines public scorecard output with internal evidence
gaps. Portfolio dashboards use aggregate pillar rollups and should not be read
as a ranking of farms.

## Portfolio Use

```bash
python3 -m services.analytics --ebf-portfolio-summary
```

The portfolio path is a messy roll-up by pillar, confidence, maturity, and
public-safe evidence. These messy roll-ups are descriptive context, not a
ranking of farms as interchangeable units.
Dashboard SQL may expose fewer maturity fields than the Python portfolio
summary, so consumers should not infer that every dashboard card contains the
full portfolio object.

## CSV Templates And Import

Templates:

- `exports/templates/ebf_scorecard_template.csv`
- `exports/templates/ebf_evidence_template.csv`

The spreadsheet bridge validates scorecard metadata and imports metadata as
draft scorecards. It validates evidence rows but does not import evidence links
into canonical `ebf_score_evidence` records. It never verifies or publishes a
scorecard.

## CIDS Mapping

EBF outputs use existing CIDS Essential Tier classes:

- `metric_definition` → `cids:Indicator`
- verified `metric_value` → `cids:IndicatorReport`
- `impact_claim` → `cids:ImpactReport`

The exporter adds `kokonut:framework = ebf`, `kokonut:ebfPillar`, and
`kokonut:cidsMapping`. No `cids:EBFScorecard` class is introduced.
There is no new CIDS class for EBF scorecards.

The exporter only reads verified `metric_value` rows. EBF scorecard records do
not automatically materialize verified metric values, so CIDS export is a
compatibility mapping rather than an automatic scorecard publication pipeline.
No EBF-specific RDF graph integration is currently defined under
`services/rdf/`.

## Agent Boundaries

| Agent/module | Actual behavior |
|-------------|-----------------|
| `ebf_scorecard_agent.py` | Returns a draft scorecard structure; does not persist the scorecard in the standalone module |
| `ebf_evidence_gap_agent.py` | Read-only evidence-gap analysis |
| `ebf_calibration_agent.py` | Returns a draft/empty calibration memo; does not persist calibration decisions |

Task-catalogue write declarations describe permitted draft outputs, not proof
that the standalone module has performed the write. Agents cannot verify or
publish scores, elevate evidence maturity to public levels, certify carbon
claims, or expose private stakeholder feedback.
Agents may not verify scores or publish scorecards.

## Limitations

- Scalar calculators are not an end-to-end scorecard pipeline.
- Score 10 is supported in Python but absent from seeded SQL rubric bands.
- Public database views are stricter than reusable Python gate helpers.
- Calibration cadence is stored but not automatically enforced by farm class.
- Evidence CSV validation does not import canonical evidence links.
- Public carbon output requires a claim and verifier, not only a carbon score.
- Portfolio output is aggregate context, not a farm ranking.
- Trust graph export is documented separately and currently has a public-safe
  connected-node filtering defect.

## Source References

- `schemas/postgres/032_ebf_scorecard.sql`
- `schemas/postgres/033_ebf_p1_operations.sql`
- `schemas/seeds/032_ebf_rubric.sql`
- `schemas/seeds/033_ebf_dashboard_datasets.sql`
- `schemas/seeds/034_ebf_p2_dashboard_datasets.sql`
- `services/scoring/calculators.py`
- `services/scoring/normalization.py`
- `services/scoring/rubric.py`
- `services/scoring/confidence.py`
- `services/scoring/gates.py`
- `services/scoring/export.py`
- `services/registry/cids_export.py`
