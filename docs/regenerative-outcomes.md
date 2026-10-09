# Regenerative Outcomes And Stewardship

Kokonut tracks reviewer-facing regenerative outcomes as governed summaries over canonical source tables. The module makes ecological, social, governance, replication, and stewardship evidence easier to review without replacing detailed source evidence or making external certification claims.

## Governance Lifecycle

All four records use the standard governed lifecycle:

```text
draft -> submitted -> verified -> published
draft -> rejected -> draft
```

Computation and agent synthesis do not verify or publish these records. Public views select only published records that satisfy their evidence and summary gates.

## Records

### `regenerative_outcome_summary`

Concise ecological and social outcomes for a location/farm and reporting period:

- `period_start`, `period_end`, and `summary_name`;
- hectares restored;
- baseline/latest species counts and diversity delta;
- baseline/latest soil carbon and carbon delta in t/ha;
- trees planted, trees surviving, and survival percentage;
- regenerative score from 0 to 100;
- jobs or roles supported, training hours, and beneficiary count;
- `evidence_confidence`: `high`, `moderate`, `low`, or `insufficient_evidence`;
- required `methodology_summary`;
- public summary, evidence maturity, metadata, and source-lineage fields.

Database checks enforce valid date ranges, non-negative counts and areas, percentages from 0 to 100, and regenerative scores from 0 to 100.

### `community_governance_mechanism`

Documents a public decision mechanism:

- governance level: `farm`, `guild`, `dao`, `network`, `publication_review`, or `other`;
- decision body and decision method;
- quorum rule;
- voting or consensus rights;
- community veto rights;
- escalation path;
- power distribution summary;
- participation cadence;
- public summary, evidence maturity, metadata, and source lineage.

Decision methods include `consensus`, `consent`, `token_vote`, `multisig`, `steward_review`, `hybrid`, and `other`.

### `replication_readiness_assessment`

Records readiness for a particular target region and farm model:

- assessment date, target region, and farm model;
- readiness score from 0 to 10;
- ecological prerequisites;
- cultural and governance prerequisites;
- infrastructure prerequisites;
- barriers, enablers, and support structures;
- minimum evidence maturity;
- replication status;
- assessment summary, public summary, evidence maturity, and metadata.

`replication_status` is one of `assessment`, `not_ready`, `conditional`, `ready_for_pilot`, `ready_for_replication`, or `blocked`. Readiness is conditional evidence, not an unlimited-scaling claim.

### `adaptive_stewardship_review`

Records periodic adaptive management:

- review date and review period;
- stewardship scope: `ecological`, `community`, `governance`, `financial`, `land`, `evidence_quality`, or `other`;
- review cadence;
- trigger thresholds and observed triggers;
- corrective actions and completion percentage;
- responsible role;
- funding continuity plan;
- next review date;
- review summary, public summary, evidence maturity, metadata, and source lineage.

Database checks enforce valid review periods and an action-completion percentage from 0 to 100.

## Public Views

| View | Public filter |
|---|---|
| `v_public_regenerative_outcome_summary` | Published, maturity >= 3, non-empty public summary, verified/published registry record |
| `v_public_community_governance_mechanism` | Published, maturity >= 3, non-empty public summary; location-scoped rows require registry backing, global rows may use `location_id IS NULL` |
| `v_public_replication_readiness_summary` | Published, maturity >= 3, non-empty public summary; no registry join is required by the view |
| `v_public_adaptive_stewardship_summary` | Published, maturity >= 3, non-empty public summary, verified/published registry record |

Public views expose evidence-maturity labels and selected metadata. They do not expose raw source evidence, private identities, or unreviewed records.

## Governed Metrics

The pilot metric definitions are:

- `hectares_restored`;
- `species_diversity_delta`;
- `soil_carbon_delta_t_ha`;
- `tree_survival_rate_pct`;
- `community_governance_participation_pct`;
- `replication_readiness_score`;
- `adaptive_stewardship_action_completion_pct`.

These are governed metric definitions, not automatically verified values. Metric computation creates draft `metric_value` rows; a human must verify values separately before public metric summaries expose them.

The metric definitions document source records, methodology, exclusions, units, and validation tests. In particular, `soil_carbon_delta_t_ha` is not automatically a public carbon-credit claim; carbon claims require separate maturity, methodology, verifier, and publication gates.

## Reports

```bash
python3 -m services.export.report_generator \
  --type regenerative_outcomes --location-id UUID
python3 -m services.export.report_generator \
  --type community_governance --location-id UUID
python3 -m services.export.report_generator \
  --type replication_readiness --location-id UUID
python3 -m services.export.report_generator \
  --type adaptive_stewardship --location-id UUID
```

Report behavior:

- `regenerative_outcomes` requires a location and supports period filtering; it returns public outcome rows and total hectares restored.
- `community_governance` accepts an optional location and includes global mechanisms when `location_id IS NULL`.
- `replication_readiness` accepts an optional location and supports assessment-date filtering.
- `adaptive_stewardship` requires a location and supports review-date filtering.

Each report includes limitations. These reports state that outcome summaries consolidate source evidence, moderate/low confidence is not external certification, governance reports exclude private identities, replication requires local ecological/cultural/governance/infrastructure/evidence review, and stewardship reviews are management evidence rather than guarantees that risks are eliminated.

## Regenerator Agent

The regenerator agent reads the four public-safe views and produces counts, a total-hectares summary, row-level public-safe records, and a synthesis:

```bash
# Read-only synthesis
python3 -m services.agents.regenerator_agent --location-id UUID

# Store an ai_summary draft for human review
python3 -m services.agents.regenerator_agent \
  --location-id UUID --store
```

- `--location-id` is optional for a network-wide public-safe synthesis.
- The agent excludes private identities and terms.
- `--store` writes `ai_summary.status = 'draft'`; it does not verify or publish the summary.
- The agent task writes only `ai_summary:draft` and remains subject to agent safety controls.
- The synthesis safety note explicitly states that replication readiness is not an unlimited-scaling claim.

## Pilot And Dashboard Assets

The Adelphi pilot seed is `schemas/seeds/040_pilot_regenerative_outcomes.sql`. It includes:

- a published, moderate-confidence regenerative outcome summary;
- a published hybrid farm-to-DAO governance mechanism;
- a published conditional replication-readiness assessment;
- a published adaptive stewardship review with corrective actions.

The pilot deliberately records boundaries such as planned rather than implemented renewable energy, conditional replication, public-summary privacy, and grant-facing evidence rather than external certification.

Metabase assets are:

| Dashboard | SQL | JSON |
|---|---|---|
| Regenerative outcomes | `dashboards/metabase/sql/44_regenerative_outcomes.sql` | `dashboards/metabase/44_regenerative_outcomes.json` |
| Community governance | `dashboards/metabase/sql/45_community_governance.sql` | `dashboards/metabase/45_community_governance.json` |
| Replication readiness | `dashboards/metabase/sql/46_replication_readiness.sql` | `dashboards/metabase/46_replication_readiness.json` |
| Adaptive stewardship | `dashboards/metabase/sql/47_adaptive_stewardship.sql` | `dashboards/metabase/47_adaptive_stewardship.json` |

Dashboard templates are imported/configured separately in Metabase. Public-safe views and governed lifecycle filters remain authoritative.

## References And Verification

- Schema and public views: `schemas/postgres/039_regenerative_outcomes_and_stewardship.sql`
- Metric definitions and dashboard dataset seed: `schemas/seeds/040_regenerative_outcomes_and_stewardship.sql`
- Adelphi pilot data: `schemas/seeds/040_pilot_regenerative_outcomes.sql`
- Report generators: `services/export/report_generator.py`
- Regenerator agent: `services/agents/regenerator_agent.py`
- Public dashboard SQL/JSON: `dashboards/metabase/44-47_*`
- Regenerative outcomes tests: `tests/test_regenerative_outcomes.py`
- Reporting governance tests: `tests/test_report_governance.py`

Run the focused suite with:

```bash
PYTHONPATH=. uv run pytest tests/test_regenerative_outcomes.py -v
```

Source tables remain canonical. Regenerative summaries, reports, dashboards, and agent outputs are governed evidence and decision-support artifacts, not automatic certification or guaranteed replication outcomes.
