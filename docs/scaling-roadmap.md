# Scaling Roadmap

Kokonut treats scaling as a staged readiness process rather than an unlimited-growth claim. Roadmap milestones document required resources, partners, dependencies, and risk gates.

## Records

| Table | Purpose |
|---|---|
| `scaling_roadmap_milestone` | Network or farm-specific scaling milestone with target region, farm model, farm count, capital needed, dependencies, risk gates, and target date |
| `v_public_scaling_roadmap_summary` | Public-safe published scaling roadmap milestones with sufficient evidence and summary text |
| `green_paper_publication_review` | Review state, open questions, approvals, and publication proof metadata for Green Paper versions |
| `v_public_green_paper_publication_status` | Public-safe Green Paper publication status |

### `scaling_roadmap_milestone`

Required fields are `roadmap_name`, `farm_model`, and `target_date`. A milestone may be network-level (`location_id` is NULL) or scoped to a location. Optional planning fields include `target_region`, `planned_farm_count`, `capital_required_usd`, `partner_requirements`, `operational_dependencies`, `risk_gates`, and `public_summary`.

The record also stores `evidence_maturity`, `metadata`, creator/updater identifiers, and timestamps. Lifecycle `status` accepts `draft`, `submitted`, `verified`, `published`, and `rejected`. `milestone_status` accepts `planned`, `in_progress`, `completed`, `blocked`, `deferred`, and `cancelled`.

Allowed `farm_model` values are `public_good_optimized`, `blended`, `for_profit`, `cooperative`, `research_pilot`, and `other`.

### Public View Gate

`v_public_scaling_roadmap_summary` includes a milestone only when:

- `status = 'published'`;
- `evidence_maturity >= 3`;
- `public_summary` is non-empty after trimming.

Unlike the public financial and risk views, this scaling view does not require a verified or published farm registry record. The view exposes planning fields, evidence maturity and label, and metadata; it does not expose the source/audit columns.

## Governed Metric

`scaling_readiness_score` is defined as a roadmap-evidence score normalized to 0–10. Its source tables are `scaling_roadmap_milestone`, `financial_sustainability_plan`, and `risk_mitigation_register`. The metric definition uses published roadmap milestones and documented risk gates, excludes unsupported unlimited-scaling claims, validates a 0–10 result, and is intended for scaling-roadmap and Green Paper reporting.

This metric is distinct from `replication_readiness_score`, which is a reviewer-assessed readiness score based on ecological, cultural, governance, infrastructure, and evidence prerequisites. Do not treat either score as a funding commitment or unlimited-growth forecast.

## Commands

```bash
python3 -m services.export.report_generator --type scaling_roadmap --location-id UUID
python3 -m services.export.report_generator --type green_paper_publication_status --location-id UUID
python3 -m services.agents.resilience_agent --location-id UUID
# Store the resilience agent output as a draft AI summary for human review
python3 -m services.agents.resilience_agent --location-id UUID --store
```

The resilience agent reads public-safe financial, risk, scaling, and Green Paper publication views. Its location-scoped summary includes matching milestones plus network-level milestones, counts milestones, identifies high or critical risks, and sums public capital requirements. With `--store`, it creates an `ai_summary` in `draft` status; the agent cannot verify or publish governed records.

Scaling roadmap entries are planning evidence. They are not commitments to launch farms unless capital, partner, operational, risk, evidence, and governance gates are satisfied. Capital requirements are projections and should not be presented as secured funding, investment offers, guaranteed returns, or a promise of commercial scale.

## Report Behavior

`generate_scaling_roadmap` reads only from `v_public_scaling_roadmap_summary`:

- With `--location-id`, it includes milestones for that location and network-level milestones where `location_id IS NULL`.
- Without a location, it includes all public milestones.
- `--period-start` and `--period-end` filter inclusively on `target_date`.
- Results are ordered by `target_date`, then `roadmap_name`.
- `total_capital_required_usd` sums `capital_required_usd` from the returned rows, treating NULL as zero.

The report limitations require capital, partner dependencies, and risk gates to be reviewed before each expansion decision. Generated reports are advisory outputs and do not approve a milestone or authorize execution.

## Green Paper Publication Review

`green_paper_publication_review` tracks a version and document path, review owner, review dates, open questions, approval records, publication CID/hash, publication timestamp, public summary, evidence maturity, metadata, and audit fields. `(version, document_path)` is unique.

Its record `status` accepts `draft`, `submitted`, `verified`, `published`, and `rejected`. Its separate `review_status` accepts:

- `draft`
- `request_for_comments`
- `stakeholder_review`
- `approved_for_publication`
- `published`
- `needs_rework`
- `superseded`

`v_public_green_paper_publication_status` includes only records with `status IN ('verified', 'published')` and a non-empty `public_summary`. It exposes review status, owner, target date, counts of open questions and approval records, publication CID/hash metadata, publication time, and evidence maturity label. Private reviewer notes are not exposed.

The `green_paper_publication_status` report returns all rows from this public view. Although the CLI accepts `--location-id`, `--period-start`, and `--period-end` through the shared report interface, the current generator does not apply those filters because publication reviews are network-level records.

## Dashboard

The public-safe scaling dashboard is:

- `dashboards/metabase/30_scaling_roadmap.json`
- SQL dataset: `dashboards/metabase/sql/30_scaling_roadmap.sql`

It is owned by the Governance Guild, marked `public_safe`, and configured for daily refresh at `06:00`. The dashboard labels rows with a NULL location as `Network-level` and displays farm model, capital, partner requirements, operational dependencies, risk gates, target date, milestone status, and public evidence fields.

## Seeded Examples

The pilot seed includes:

- `Adelphi replication readiness`, a location-scoped blended milestone for two additional Dominican pilot farms, targeted for 2026-12-31.
- `Public-goods farm playbook`, a network-level `public_good_optimized` milestone for a Celo/Gnosis-aligned ReFi partner network, targeted for 2027-06-30.

Both examples are published with evidence maturity 3 but remain roadmap milestones, not guaranteed expansion commitments.

## References And Tests

- Schema and public views: `schemas/postgres/035_financial_resilience_and_scaling.sql`
- Metric and dashboard seed: `schemas/seeds/036_financial_resilience_and_scaling.sql`
- Pilot examples: `schemas/seeds/030_pilot_financial_resilience.sql`
- Report generator: `services/export/report_generator.py`
- Resilience agent: `services/agents/resilience_agent.py`
- Dashboard: `dashboards/metabase/30_scaling_roadmap.json`
- SQL dataset: `dashboards/metabase/sql/30_scaling_roadmap.sql`
- Focused tests: `tests/test_financial_resilience.py`, `tests/test_financial_enhancements.py`, and `tests/test_open_source_capitalist_scaling.py`
