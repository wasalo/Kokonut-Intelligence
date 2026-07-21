# EBF Implementation Memo

This memo records the Evidence-Based Framework (EBF) implementation boundary:
what is stored, calculated, calibrated, exported, published, and still requires
human or third-party review. EBF scorecards are governed records, not an
autonomous certification system.

## Implementation Status

| Capability | Status | Boundary |
|------------|--------|----------|
| Seven-pillar rubric | Implemented | Seeded definitions and score bands |
| Scalar calculators | Implemented | Accept inputs and return scores; do not persist scorecards |
| Scorecard schema | Implemented | Governed lifecycle and public-safe views |
| Evidence links | Implemented | Links and score maturity support publication gates |
| Confidence labels | Implemented | Derived from evidence count, maturity, and public-safe evidence |
| Calibration records | Schema-supported | Tables and views exist; human/third-party process remains required |
| Trust graph export | Implemented/manual | One-hop export and Mermaid rendering; no graph population service |
| Public report | Implemented/manual | `ebf_scorecard` report reads public views |
| Agent scorecard drafting | Draft/read-only | Standalone agent returns a draft structure; it does not persist it |
| CIDS mapping | Implemented/export | Maps verified `metric_value` rows, not scorecards directly |

## Reused Foundations

- `impact_framework` and `impact_dimension` define framework metadata.
- `metric_definition` and `metric_value` remain the governed semantic layer for
  metric outputs.
- `evidence_maturity_level` provides the maturity reference model.
- `stakeholder_feedback` and `stakeholder_outcome` support equity and community
  evidence with privacy controls.
- `report_snapshot`, `dashboard_dataset`, and Metabase SQL provide delivery
  paths.
- `services.registry.cids_export` maps verified metrics to CIDS classes.
- `services.agents.safety` and `services.agents.tasks` define agent limits.

## New EBF Foundation

The new EBF foundation is the scorecard, rubric, evidence-link, calibration,
recommendation, and trust-graph schema described below.

`schemas/postgres/032_ebf_scorecard.sql` defines:

- `ebf_pillar`
- `ebf_rubric_band`
- `ebf_scorecard`
- `ebf_score`
- `ebf_score_evidence`
- `v_public_ebf_scorecard`
- `v_public_ebf_scorecard_summary`
- `v_public_ebf_pillar_summary`

`schemas/postgres/033_ebf_p1_operations.sql` defines:

- `ebf_farm_metric_profile`
- `ebf_calibration_session`
- `ebf_calibration_decision`
- `ebf_trust_graph_node`
- `ebf_trust_graph_edge`
- `ebf_improvement_recommendation`
- internal evidence-gap and calibration-history views

Migration `042_fk_index_fixes.sql` adds EBF foreign-key indexes. No later
migration substantially changes the EBF tables or public views.

## Seven Pillars

The seed file `schemas/seeds/032_ebf_rubric.sql` defines:

1. `air_quality`
2. `water_management`
3. `soil_health`
4. `biodiversity`
5. `carbon_sequestration`
6. `equity_community`
7. `implementation_quality`

Framework mappings place air, water, soil, and biodiversity under environmental
impact; carbon and implementation under sustainability; and equity/community
under social impact. The existing `ebf_economic` framework dimension is not
assigned an EBF pillar by the seed.

## Rubric And Scoring Boundary

Python rubric helpers label scores as:

| Score | Label |
|-------|-------|
| 0–1 | `insufficient` |
| 2–3 | `emerging` |
| 4–5 | `developing` |
| 6–7 | `strong` |
| 8–10 | `leading` |

The SQL seed uses `generate_series(0, 9)`, producing 10 bands per pillar and 70
rows total. It does not seed a score-10 band even though Python clamps and labels
score 10 as `leading`. This seed/runtime discrepancy should be resolved before
claiming that the database rubric is complete through score 10.

The calculators in `services/scoring/calculators.py` accept scalar inputs:

| Pillar | Calculation input |
|--------|-------------------|
| Air quality | kg CO2e per acre, normalized over 0–5000 |
| Water management | runoff reduction percentage, normalized over 0–100 |
| Soil health | soil-carbon change percentage, normalized over -2–8 |
| Biodiversity | species richness index, normalized over 0–100 |
| Carbon sequestration | total farm CO2e divided by area, normalized over 0–20 |
| Equity/community | local-worker percentage and training hours per worker |
| Implementation quality | SMART KPI completion percentage |

They return scalar scores. They do not fetch governed metrics, create
`ebf_score` rows, compute a complete scorecard, or publish anything. The equity
feedback helper is a separate database-backed heuristic that uses aggregate
verified/published stakeholder feedback without returning raw feedback text.

## Confidence

`services/scoring/confidence.py` derives evidence confidence from evidence count,
overall maturity, and public-safe evidence count:

| Condition | Label |
|-----------|-------|
| No evidence or maturity ≤1 | `insufficient_evidence` |
| Maturity ≥5, at least 3 rows, at least 2 public-safe | `high` |
| Maturity ≥4, at least 2 rows, at least 1 public-safe | `moderate` |
| Other evidence states | `low` |

Scorecard confidence is derived from pillar labels: any insufficient pillar makes
the scorecard insufficient; all high is high; high/moderate combinations are
moderate; remaining combinations are low.

## Lifecycle And Calibration

EBF scorecards use:

```text
draft → submitted → verified → published
                  ↘ rejected
```

Calibration phase is separate from lifecycle `status`. Calibration records use
their own tables and metadata. Supported calibration methods are:

- `third_party`
- `team_with_report`
- `mixed_panel`

Supported cadence values are `annual`, `semi_annual`, `quarterly`, and `custom`.
The schema stores these values, but it does not enforce that pilot farms use
semi-annual calibration or network farms use annual calibration. Those are
operational recommendations, not automatic rules.

Published or verified calibration records require the applicable report URL or
report hash when the schema marks a calibration report as required. Calibration
does not itself verify a score or raise its evidence maturity.

## Publication Gates

The database public views require more than a scorecard maturity value. Public
eligibility includes:

- `ebf_scorecard.status = 'published'`
- `ebf_scorecard.public_claim_allowed = TRUE`
- scorecard evidence maturity at least 4
- seven pillar score rows
- public-enabled pillar scores
- pillar score maturity at least 4
- at least one evidence link for each public pillar
- verified or published `farm_registry_record`

Public carbon pillar scores additionally require:

- evidence maturity exactly 6
- an evidence link
- a linked claim with `claim_category = 'carbon'`
- `claim_type = 'third_party_verified_claim'`
- claim status `published`
- external verifier
- methodology reference

The Python helpers in `services/scoring/gates.py` are reusable advisory checks,
but they do not reproduce every database-view condition. In particular,
`scorecard_publication_gate()` checks supplied scorecard and pillar results but
does not independently enforce lifecycle status, public-claim flag, registry
status, seven-pillar completeness, or every view join.

The public views require an evidence link but do not independently require the
linked `ebf_score_evidence.evidence_maturity_level` to be at least 4; the public
threshold is applied to the score/pillar maturity field.

## Dashboards And Reports

Dashboard datasets are seeded in:

- `schemas/seeds/033_ebf_dashboard_datasets.sql`
- `schemas/seeds/034_ebf_p2_dashboard_datasets.sql`

Assets include:

- `dashboards/metabase/22_ebf_scorecard.json`
- `dashboards/metabase/24_portfolio_ebf.json`
- scorecard, evidence-gap, calibration-history, and portfolio SQL cards

The scorecard report is:

```bash
python3 -m services.export.report_generator \
  --type ebf_scorecard --location-id UUID
```

It reads public scorecard views and does not expose internal calibration or
private evidence. No separate EBF portfolio report generator exists. Portfolio
dashboard output is an aggregate roll-up by pillar and public-safe evidence;
it is not a ranking of farms as interchangeable units. Dashboard SQL exposes
less maturity detail than some dataset metadata describes.

## CSV And Spreadsheet Bridge

Templates:

- `exports/templates/ebf_scorecard_template.csv`
- `exports/templates/ebf_evidence_template.csv`

The bridge validates scorecard metadata and imports scorecard metadata as draft
scorecards. Evidence rows are validated but are not imported into canonical
`ebf_score_evidence` records by the current bridge. The bridge does not verify or
publish scorecards.

## CIDS And Linked Data

The CIDS exporter maps verified EBF metric outputs:

- `metric_definition` → `cids:Indicator`
- verified `metric_value` → `cids:IndicatorReport`
- `impact_claim` → `cids:ImpactReport`

It adds metadata such as `kokonut:framework = ebf`, `kokonut:ebfPillar`, and
`kokonut:cidsMapping`. No new CIDS EBF scorecard class is introduced.

The scorecard system does not automatically create the required verified
`metric_value` rows. CIDS is therefore an export/compatibility mapping, not an
automatic scorecard-to-CIDS publication pipeline. No EBF-specific RDF graph
builder integration was found under `services/rdf/`.

## Agent Boundaries

| Agent | Actual behavior |
|-------|-----------------|
| EBF scorecard agent | Returns a draft scorecard structure; standalone module does not persist it |
| Evidence-gap agent | Read-only analysis from evidence-gap views |
| Calibration agent | Returns an empty/draft calibration memo; does not persist decisions |

The task catalogue declares draft outputs for some agents, but declarations do
not imply that the standalone module has already performed the write. Safety
rules prohibit publication, verification, evidence-maturity elevation beyond
the permitted draft boundary, carbon certification, and exposure of private
stakeholder feedback.

## Remaining Scope Boundaries

- Scalar calculators are not human calibration or third-party review.
- Public-view gates are stricter than reusable Python helper gates.
- Rubric score 10 requires seed correction for database parity.
- Trust graph exports are not a graph population service.
- Public-safe trust graph node filtering currently has a connected-node defect;
  see `docs/ebf-trust-graph.md`.
- Portfolio roll-ups are descriptive and should not be interpreted as farm
  rankings.
- Agents propose drafts and evidence gaps; they do not certify outcomes.

## Source References

- `schemas/postgres/032_ebf_scorecard.sql`
- `schemas/postgres/033_ebf_p1_operations.sql`
- `schemas/seeds/032_ebf_rubric.sql`
- `schemas/seeds/033_ebf_dashboard_datasets.sql`
- `schemas/seeds/034_ebf_p2_dashboard_datasets.sql`
- `services/scoring/calculators.py`
- `services/scoring/confidence.py`
- `services/scoring/gates.py`
- `services/scoring/export.py`
- `services/scoring/trust_graph.py`
- `services/agents/ebf_scorecard_agent.py`
- `services/agents/ebf_evidence_gap_agent.py`
- `services/agents/ebf_calibration_agent.py`
