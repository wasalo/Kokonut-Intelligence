# EBF Implementation Memo

This memo records the schema inventory and implementation decisions for the EBF scorecard sequence.

## Reused Foundations

- `impact_framework` and `impact_dimension` already define EBF and its four existing dimensions.
- `metric_definition` and `metric_value` remain the governed semantic layer for score outputs.
- `evidence_maturity_level` provides the 0-6 publication gate used by EBF scorecards.
- `stakeholder_feedback` and `stakeholder_outcome` support the equity and community pillar with privacy controls.
- `report_snapshot`, `dashboard_dataset`, and Metabase SQL files provide existing dashboard/report delivery paths.
- `services.registry.cids_export` already maps verified metric values to `cids:IndicatorReport`.
- `services.agents.safety` and `services.agents.tasks` provide bounded agent task definitions and review limits.

## New EBF Foundation

- `schemas/postgres/032_ebf_scorecard.sql` defines pillars, rubric bands, scorecards, pillar scores, evidence links, and public-safe views.
- `schemas/postgres/033_ebf_p1_operations.sql` defines metric profiles, calibration sessions, calibration decisions, trust graph records, recommendations, and internal review views.
- `schemas/seeds/032_ebf_rubric.sql` seeds seven pillars, default 0-10 rubric bands, and CIDS-compatible score metric definitions.
- `schemas/seeds/033_ebf_dashboard_datasets.sql` and `034_ebf_p2_dashboard_datasets.sql` register EBF dashboard datasets.

## Key Decisions

- EBF scorecards use canonical lifecycle states: `draft`, `submitted`, `verified`, `published`, `rejected`.
- Calibration phase details live in calibration tables and metadata, not in lifecycle `status`.
- Public EBF scorecards require evidence maturity Level 4 or higher.
- Public carbon pillar scores require Level 6.
- EBF score outputs map to `cids:IndicatorReport` through `metric_value`; no new CIDS class is introduced.
- Portfolio views use messy roll-ups by pillar, confidence, and maturity. They must not rank farms as interchangeable units.
- Agents may draft, summarize, and identify gaps. Agents may not verify, publish, raise evidence maturity, certify carbon claims, or expose private feedback.

## Remaining Scope Boundaries

- Current scoring calculators normalize governed metric inputs. They are not a replacement for human calibration or third-party review.
- Dashboard JSON files are lightweight Metabase definitions intended to mirror SQL files and dataset seeds.
- Trust graph exports support JSON and Mermaid text. Public exports must use public-safe nodes and edges only.
