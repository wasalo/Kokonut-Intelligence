# Open Source Capitalist Scaling

The Open Source Capitalist layer records the economics, risks, barriers, and
reuse signals involved in scaling regenerative farm operations. It helps
reviewers ask questions such as:

- What might it cost to launch or replicate a farm model?
- Which scaling targets are planned, conditional, or blocked?
- What barriers could prevent adoption?
- How resilient is the model under downside scenarios?
- Which schemas, dashboards, reports, agents, contracts, playbooks, and
  datasets are reusable?

These records are governed planning and evidence records. They do not turn a
roadmap into a promise, a scenario into a guarantee, or an open-source artifact
into proof of external adoption.

## Records

The schema was introduced by migration `040_open_source_capitalist_scaling.sql`.

| Table | Purpose |
|---|---|
| `farm_launch_unit_economics` | Setup, first-year operations, verification overhead, launch cost, unit costs, projected revenue/NOI, ROI, payback, timeline, assumptions, and evidence confidence for a farm model. |
| `network_scaling_target` | A dated network target with farm model, target farms/hectares/beneficiaries, required capital, readiness, dependencies, risk gates, and target status. |
| `adoption_barrier_assessment` | A categorized barrier covering onboarding, governance, regulation, culture, market, technology, capital, or evidence quality, with severity, likelihood, owner, mitigation, and resolution status. |
| `perpetual_value_stress_test` | A downside scenario covering revenue, cost, grant delay, yield, runway, NOI, solvency, and mitigation actions. |
| `open_source_impact_artifact` | A reusable schema, dashboard, agent, report, playbook, contract, export mapping, dataset, or other artifact with version, license, reuse status, and reuse count. |

All five tables use the governed lifecycle:

```text
draft -> submitted -> verified -> published
                    \-> rejected
```

Agents may create draft outputs where their task policy allows it, but they
cannot verify or publish these records.

### Controlled Values

- Farm models: `public_good_optimized`, `blended`, `for_profit`, `cooperative`,
  `research_pilot`, or `other`.
- Scaling target status: `planned`, `conditional`, `in_progress`, `achieved`,
  `blocked`, `deferred`, or `cancelled`.
- Barrier categories: `farmer_onboarding`, `dao_governance`, `regulatory`,
  `cultural`, `market`, `technical`, `capital`, `evidence_quality`, or `other`.
- Barrier scopes: `farm`, `community`, `region`, `network`, `partner`, or
  `other`.
- Barrier resolution: `open`, `mitigating`, `resolved`, `accepted`, or
  `blocked`.
- Stress types: `market_downturn`, `grant_delay`, `cost_inflation`,
  `yield_shock`, `climate_event`, `dao_funding_delay`, `combined_downside`, or
  `other`.
- Stress solvency: `untested`, `resilient`, `watchlist`, `needs_mitigation`, or
  `insolvent_without_support`.
- Artifact types: `schema`, `dashboard`, `agent`, `report`, `playbook`,
  `contract`, `export_mapping`, `dataset`, or `other`.
- Artifact reuse: `available`, `in_use`, `pilot_reuse`, `deprecated`, or
  `maintenance_needed`.

## Public Views

Each public view exposes only records that are:

- `status = 'published'`
- Evidence maturity level 3 or higher
- Backed by a non-empty `public_summary`

Location-scoped launch economics, barriers, and stress tests additionally
require a related `farm_registry_record` with status `verified` or `published`.
Network-level scaling targets and open-source artifacts are not location-scoped
and do not require a location registry join.

| View | Exposes |
|---|---|
| `v_public_farm_launch_unit_economics` | Public launch costs, unit economics, assumptions, confidence, and projected returns. |
| `v_public_network_scaling_target` | Public targets plus derived capital required per farm. |
| `v_public_adoption_barrier_assessment` | Public barrier category, scope, mitigation, ownership, and resolution context. |
| `v_public_perpetual_value_stress_test` | Public downside assumptions, runway, NOI, solvency status, and mitigation actions. |
| `v_public_open_source_impact_artifact` | Public artifact identity, location in the repository or external URL, license, version, reuse status/count, and supported uses. |

Private capital terms, raw stakeholder concerns, unpublished commitments, and
non-public source records are not exposed through these views.

## Domain Metric Definitions

Seed `041_open_source_capitalist_scaling.sql` defines eight active metric
definitions:

| Metric | Definition | Interpretation |
|---|---|---|
| `farm_launch_cost_usd` | `total_launch_cost_usd` from launch economics | Estimated total setup, first-year operating, and verification overhead. |
| `cost_per_planned_farm_usd` | Launch cost divided by planned farm count | Estimated capital per planned farm where the denominator is positive. |
| `projected_roi_pct` | Projected annual NOI divided by launch cost times 100 | Scenario-based projected return, not a guaranteed return. |
| `cost_per_beneficiary_usd` | Launch cost divided by expected public-safe beneficiaries | Aggregate planning cost per expected beneficiary. |
| `cost_per_hectare_restored_usd` | Launch cost divided by planned or documented hectares | Planning cost per hectare, excluding unsupported expansion acreage. |
| `downside_runway_months` | Stress-test downside runway | Remaining runway under a published downside scenario. |
| `adoption_barrier_resolution_pct` | Resolved plus mitigating barriers divided by total barriers | Public barrier resolution signal by scope or category. |
| `open_source_artifact_reuse_count` | `reuse_count` from published artifacts | Observed or documented reuse signal for a public artifact. |

These are governed semantic definitions used by scaling reports, dashboards,
and related analytics. They are not currently registered in the standard
`services.metrics.calculators.CALCULATORS` registry, so they should not be
described as outputs currently computed by the normal `services.metrics
--compute` engine. Their source records and public views remain subject to the
domain's publication gates.

## Reports And Dashboards

Generate public-safe reports with the report generator:

```bash
python3 -m services.export.report_generator \
  --type scaling_economics --location-id UUID
python3 -m services.export.report_generator \
  --type adoption_barriers --location-id UUID \
  --period-start 2026-01-01 --period-end 2026-12-31
python3 -m services.export.report_generator \
  --type perpetual_value_stress --location-id UUID
python3 -m services.export.report_generator \
  --type open_source_impact
```

The report types are:

- `scaling_economics`: location-compatible launch economics plus network
  targets, with total launch cost, target capital, planned farms, and target
  farms.
- `adoption_barriers`: public barriers and an active barrier count, filtered by
  location and assessment period when supplied.
- `perpetual_value_stress`: public scenarios and a watchlist/mitigation count,
  filtered by location and scenario period when supplied.
- `open_source_impact`: public artifacts and total reuse count.

The open-source artifact report currently reads all public artifacts. Its
`location_id` and period arguments are retained in the report interface but do
not filter the artifact query because artifacts are network-level records.

The seed registers four published dashboard datasets, each with a 1,440-minute
refresh interval:

| Dataset | SQL | Dashboard |
|---|---|---|
| Scaling Economics Summary | `dashboards/metabase/sql/48_scaling_economics.sql` | `dashboards/metabase/48_scaling_economics.json` |
| Adoption Barriers Summary | `dashboards/metabase/sql/49_adoption_barriers.sql` | `dashboards/metabase/49_adoption_barriers.json` |
| Perpetual Value Stress Tests | `dashboards/metabase/sql/50_perpetual_value_stress.sql` | `dashboards/metabase/50_perpetual_value_stress.json` |
| Open Source Impact Artifacts | `dashboards/metabase/sql/51_open_source_impact.sql` | `dashboards/metabase/51_open_source_impact.json` |

Reports are public-safe projections, not automatic publication of the source
records. Stored report snapshots begin as drafts and retain their own review,
hash, uncertainty, and public-interest context.

## Synthesis Agent

Run the Open Source Capitalist synthesis agent:

```bash
python3 -m services.agents.open_source_capitalist_agent --location-id UUID
python3 -m services.agents.open_source_capitalist_agent \
  --location-id UUID --store
```

The agent reads only the five public views and summarizes:

- Launch economics count, planned farm count, and total launch cost
- Network target count and target farm count
- Adoption barrier count and active barrier count
- Stress-test count and watchlist/mitigation count
- Published artifact count and reuse signals

Without `--store`, the result is read-only. With `--store`, it creates an
`ai_summary` row with status `draft` for human review. It cannot verify,
publish, issue credits, make financial commitments, or claim external
integrations that lack canonical governed records.

The agent's safety note explicitly treats planned farm counts as non-live
claims, ROI as non-guaranteed, private capital terms as excluded, and external
integrations as unclaimed until supported by governed records.

## Pilot Boundaries

The curated pilot seed is
`schemas/seeds/041_pilot_open_source_capitalist_scaling.sql`. Its records use
planned or conditional economics and explicitly avoid claims that expansion
farms are already operating.

Pilot data must not be read as evidence of:

- Two or more already-operating farms based only on a scaling target.
- Guaranteed ROI, payback, solvency, or capital availability.
- External adoption of an artifact based only on a reuse count.
- Hypercert, Ecocertain, or other external integration without canonical
  records.

## Interpretation Boundaries

- Roadmap targets are not registry-backed operating counts unless separately
  supported by farm records.
- ROI and payback are scenario evidence, not securities offerings or guaranteed
  returns.
- Stress tests are planning evidence and should be refreshed as market,
  climate, cost, yield, and governance assumptions change.
- Barrier mitigation cost is an estimate unless supported by verified expense
  records.
- Reuse counts are governed signals, not proof of third-party adoption.
- Public summaries do not expose raw private stakeholder concerns or private
  financing terms.
- A metric definition is not proof that the standard metric engine currently
  computes the metric.

## Sources And Tests

- `schemas/postgres/040_open_source_capitalist_scaling.sql`
- `schemas/seeds/041_open_source_capitalist_scaling.sql`
- `schemas/seeds/041_pilot_open_source_capitalist_scaling.sql`
- `services/export/report_generator.py`
- `services/agents/open_source_capitalist_agent.py`
- `services/agents/tasks.py`
- `services/agents/safety.py`
- `dashboards/metabase/sql/48_scaling_economics.sql`
- `dashboards/metabase/sql/49_adoption_barriers.sql`
- `dashboards/metabase/sql/50_perpetual_value_stress.sql`
- `dashboards/metabase/sql/51_open_source_impact.sql`

Run the focused test suite:

```bash
python3 -m pytest tests/test_open_source_capitalist_scaling.py -v
```
