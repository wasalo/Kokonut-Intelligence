# Holistic Wellbeing And Cultural Context

Kokonut records holistic wellbeing as governed, privacy-safe evidence. The
module makes cultural context, local-language accessibility, community
participation, and wellbeing signals explicit without exposing raw private
stakeholder feedback or unrestricted cultural knowledge.

These records are evidence and learning signals. They are not clinical
assessments, universal wellbeing certifications, proof of cultural equivalence,
or proof that every stakeholder has received an outcome.

## Records

The module has three governed record types:

| Table | Purpose | Key fields |
|---|---|---|
| `cultural_context_record` | Public-safe summaries of local-language needs, traditional knowledge, heritage species, community stories, and land-memory context | `practice_name`, `practice_type`, `stakeholder_group`, `language`, `consent_scope` |
| `wellbeing_metric_observation` | Governed observations for operator capability, community trust, worker safety, training access, and related wellbeing metrics | `metric_key`, `observation_date`, `score_value`/`count_value`/`text_value` |
| `participatory_action_record` | Traceability from stakeholder feedback to follow-up actions, metric proposals, report changes, or governance review | `action_type`, `action_date`, `decision_status`, linked record IDs |

Every record requires a `location_id` and may optionally reference a `farm_id`.
Records also carry lifecycle state, evidence maturity, provenance fields, and
JSON metadata. Source payloads and raw records remain governed and are not
automatically public.

## Lifecycle And Evidence

All three tables use the governed lifecycle:

```text
draft -> submitted -> verified -> published
                         \-> rejected
```

Lifecycle status is separate from domain state. For example, a cultural record
can be `status = 'published'` while its content describes a planned practice,
and a participatory action can be published while its `decision_status` remains
`planned` or `in_progress`.

Evidence maturity is a separate field from lifecycle status. Public visibility
requirements differ by view and are documented below; do not assume that every
public view uses the same maturity or summary gate.

## Cultural Context

### Practice Types

`cultural_context_record.practice_type` is constrained to:

```text
traditional_knowledge
local_language
heritage_species
cultural_practice
community_story
land_memory
education
other
```

The record stores a practice name and description, an optional stakeholder group
and language, optional evidence URLs and hashes, and a public summary when
publication is authorized.

### Public Opt-In

The schema requires these conditions whenever `is_public = TRUE`:

1. `consent_given = TRUE`.
2. `consent_scope` is `public_summary`, `public_quote`, or `public_full`.
3. `status = 'published'`.
4. `public_summary` is non-empty.

The public view additionally requires a related `farm_registry_record` for the
location with status `verified` or `published`.

Raw cultural knowledge, private stories, and non-consented material must remain
private. A public summary is a bounded representation of the source record, not
permission to publish the source description or raw evidence.

## Wellbeing Metric Observations

`wellbeing_metric_observation` records a metric observation for a location and
date. It can include:

- a metric key and display name from `metric_definition`;
- stakeholder group and language;
- numeric `score_value`;
- integer `count_value`;
- qualitative `text_value`;
- public summary;
- source table and source record identifiers;
- evidence maturity and lifecycle status.

At least one of `score_value`, `count_value`, or non-empty `text_value` is
required by the schema. The table itself does not impose a universal score
range; metric definitions carry metric-specific validation rules. For example,
the seeded score metrics use `0-10` validation, percentages use `0-100`, and
training hours require a non-negative value.

The public view exposes published observations with evidence maturity at least
`3` and a verified or published farm registry record. It does not require a
non-empty `public_summary` at the SQL view level, so callers must treat a null
summary as a publication-quality gap rather than inventing a narrative.

## Participatory Actions

`participatory_action_record` links community voice to a governed follow-up. It
can reference:

- `stakeholder_feedback_id`;
- `metric_proposal_id`;
- `report_snapshot_id`.

Supported `action_type` values are:

```text
feedback_response
metric_proposal
report_change
governance_review
operator_summary
community_meeting
training_followup
other
```

Supported `decision_status` values are:

```text
draft, planned, in_progress, completed, deferred, rejected
```

The public view requires `status = 'published'`, a non-empty `public_summary`,
and a verified or published farm registry record. It does not impose the
`evidence_maturity >= 3` condition used by the wellbeing metric view.

The view may include bounded joined metadata such as feedback type, sentiment,
metric name, and metric proposal status. It does not expose raw feedback text.
Use the public action summary and decision state to describe traceability; do
not infer that every linked feedback item was resolved or that a proposal was
implemented.

## Public Views

| View | Public gate | Main output |
|---|---|---|
| `v_public_cultural_context_summary` | `is_public = TRUE`, consent given, published status, non-empty public summary, verified/published registry | Practice name/type, group, language, public summary, maturity |
| `v_public_wellbeing_metric_summary` | Published status, evidence maturity `>= 3`, verified/published registry | Metric key/name, date, group, language, score/count, summary, maturity |
| `v_public_participatory_governance_summary` | Published status, non-empty public summary, verified/published registry | Action, date, group, bounded feedback/proposal metadata, decision state, summary, maturity |

All three views join `evidence_maturity_level` for a human-readable
`evidence_maturity_label`. Public views are location-scoped through the
registry-record requirement, but they do not replace consent, stakeholder
review, or the underlying governance workflow.

## Governed Metrics

The holistic wellbeing seed defines these seven active metrics:

| Metric | Meaning | Unit/frequency |
|---|---|---|
| `operator_capability_score` | Reviewed skills, confidence, and practical regenerative-system capability | `score_0_10`, quarterly |
| `local_language_reporting_coverage` | Share of expected operator reports available in the working language | percentage, monthly |
| `community_trust_signal` | Aggregate privacy-safe trust, review coverage, and resolved-concern signal | `score_0_10`, quarterly |
| `worker_safety_signal` | Reviewed safety conditions, unresolved harms, and corrective-action follow-through | `score_0_10`, quarterly |
| `training_access_hours` | Governed practical training, field learning, or capacity-building hours | hours, monthly |
| `benefit_distribution_transparency` | Visibility of benefit allocation, public-goods commitments, and value-flow rules | `score_0_10`, quarterly |
| `cultural_capital_activity_count` | Published, consented cultural-context and related cultural activity count | count, quarterly |

Metric rules exclude raw private feedback, household-level observations,
unreviewed allegations, unsupported translation promises, and informal values
without source lineage.

### Related GNH Metrics

The later GNH alignment seed defines related but distinct metrics such as
`local_language_access_coverage_pct`, `foundational_wellbeing_score`, and
`peace_and_safety_signal`. Do not treat those keys as aliases for the holistic
wellbeing metrics. Use the metric key and its registered definition when
interpreting a `metric_value` row or report.

Metric computation creates draft, unverified `metric_value` rows. Running a
computation is not human verification or public publication.

## Reports

Generate the public-safe holistic wellbeing report with:

```bash
python3 -m services.export.report_generator \
  --type holistic_wellbeing \
  --location-id UUID
```

The report returns:

- `report_type = 'holistic_wellbeing'`;
- location ID and name;
- distinct languages found in public cultural and wellbeing rows;
- `cultural_context` rows;
- `wellbeing_metrics` rows;
- `participatory_actions` rows;
- limitations;
- generation timestamp.

Optional date filters are available:

```bash
python3 -m services.export.report_generator \
  --type holistic_wellbeing \
  --location-id UUID \
  --period-start 2026-01-01 \
  --period-end 2026-12-31
```

Date filtering applies to `wellbeing_metric_observation.observation_date` and
`participatory_action_record.action_date`. Cultural context records have no
date column in this schema and are returned for the location regardless of the
period arguments.

The report explicitly limits interpretation to public-safe summaries and
aggregate signals. It excludes private stakeholder feedback, household-level
observations, and non-consented cultural knowledge. Wellbeing metrics are
learning signals unless externally verified by a named reviewer or methodology.

## Wellbeing Synthesis Agent

Run the public-safe synthesis agent for one location:

```bash
python3 -m services.agents.wellbeing_agent --location-id UUID
```

The `--location-id` argument is required. The agent does not provide an
all-location mode.

To store the generated narrative as a draft `ai_summary`:

```bash
python3 -m services.agents.wellbeing_agent \
  --location-id UUID \
  --store
```

The agent reads:

- `v_public_cultural_context_summary`;
- `v_public_wellbeing_metric_summary`;
- `v_public_participatory_governance_summary`;
- aggregate language counts from non-rejected `stakeholder_feedback` rows.

The language query returns counts by language and separates total feedback from
rows with `consent_given = TRUE AND is_public = TRUE`. It does not select raw
feedback text.

The output summary contains:

- `cultural_context_count`;
- `wellbeing_metric_count`;
- `participatory_action_count`;
- distinct `languages`;
- `cultural_context` rows;
- `wellbeing_metrics` rows;
- `participatory_actions` rows;
- `language_coverage` aggregate rows;
- synthesized text;
- a safety note.

The catalogue entry is `holistic_wellbeing_synthesis`:

- risk: medium;
- required input: `location_id` UUID;
- optional input: `store`;
- required output: `summary` object;
- optional output: `ai_summary_id` UUID;
- permitted write: `ai_summary:draft` only;
- high risk: false.

The agent cannot verify, publish, attest, or change the underlying cultural,
wellbeing, feedback, or participatory records. Stored summaries require human
review before any publication workflow.

## Dashboards

The seed registers two published dashboard datasets with a 1,440-minute refresh
interval and public-safe metadata:

| Dataset | SQL | Dashboard |
|---|---|---|
| Holistic Wellbeing Summary | `dashboards/metabase/sql/26_holistic_wellbeing.sql` | `dashboards/metabase/26_holistic_wellbeing.json` |
| Participatory Governance Traceability | `dashboards/metabase/sql/27_participatory_governance.sql` | `dashboards/metabase/27_participatory_governance.json` |

`26_holistic_wellbeing.sql` combines public wellbeing metric rows and cultural
context rows with `UNION ALL`. Cultural rows are represented as a count-like
`cultural_context` metric with no observation date.

`27_participatory_governance.sql` displays public action summaries together with
bounded feedback type, sentiment, metric proposal, decision status, and evidence
maturity fields.

Dashboard queries read the public views. Dashboard access must not bypass the
view filters or expose raw source records.

## Adelphi Pilot Evidence

The pilot accountability seed contains examples linking:

- Spanish operator summaries and local-language reporting;
- operator capability observations;
- community trust and worker-safety signals;
- training access and cultural-context records;
- participatory actions connected to feedback and metric proposals.

These records demonstrate traceability, not universal impact. Adelphi examples
must preserve the following boundaries:

- local-language coverage is evidence of reported delivery, not proof that all
  participants can access every workflow;
- operator capability and trust are aggregate learning signals;
- cultural records require public consent and published lifecycle state;
- participation records show documented follow-up, not guaranteed resolution;
- private feedback, raw cultural knowledge, household observations, and
  unreviewed harm claims remain excluded from public output.

## Privacy And Governance Rules

1. Keep raw cultural knowledge and raw stakeholder feedback private unless the
   applicable consent scope explicitly permits the bounded public output.
2. Do not publish household-level, individual protected-class, disability, or
   identity details through these views, reports, dashboards, or agents.
3. Use `public_summary` for a reviewed, purpose-limited representation of source
   evidence; do not copy raw source text into it.
4. Distinguish lifecycle status from implementation or decision status.
5. Treat public wellbeing metrics as evidence signals, not clinical or external
   certification.
6. Treat participatory traceability as evidence of a recorded follow-up path,
   not proof that a concern was resolved.
7. Require human review before publishing agent-generated summaries.
8. Preserve metric definitions and source lineage when changing calculations or
   public interpretation.

## Commands And References

Primary commands:

```bash
python3 -m services.agents.wellbeing_agent --location-id UUID
python3 -m services.agents.wellbeing_agent --location-id UUID --store
python3 -m services.export.report_generator --type holistic_wellbeing --location-id UUID
```

Implementation references:

- `schemas/postgres/034_holistic_wellbeing.sql`
- `schemas/seeds/035_holistic_wellbeing.sql`
- `schemas/seeds/029_pilot_impact_accountability.sql`
- `services/agents/wellbeing_agent.py`
- `services/agents/tasks.py`
- `services/export/report_generator.py`
- `dashboards/metabase/sql/26_holistic_wellbeing.sql`
- `dashboards/metabase/sql/27_participatory_governance.sql`

Tests:

- `tests/test_holistic_wellbeing.py`
- `tests/test_agent_tasks.py`
- `tests/test_state_of_kokonut.py`
