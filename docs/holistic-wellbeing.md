# Holistic Well-being And Cultural Context

Kokonut tracks holistic well-being as governed, privacy-safe evidence. The module makes cultural context, local-language accessibility, community participation, and well-being signals explicit without exposing raw private stakeholder feedback.

## Records

| Table | Purpose |
|---|---|
| `cultural_context_record` | Public-safe summaries of local-language needs, traditional knowledge, heritage species, community stories, and land-memory context |
| `wellbeing_metric_observation` | Governed observations for well-being metrics such as operator capability, community trust, worker safety, and training access |
| `participatory_action_record` | Traceability from feedback to follow-up actions, metric proposals, report changes, or governance review |

## Public Views

| View | Purpose |
|---|---|
| `v_public_cultural_context_summary` | Published, consented cultural-context summaries only |
| `v_public_wellbeing_metric_summary` | Published well-being metric observations with evidence maturity >= 3 |
| `v_public_participatory_governance_summary` | Public-safe feedback-to-action traceability |

## Privacy Rules

- Raw cultural knowledge and raw stakeholder feedback remain private unless explicit consent permits publication.
- Public cultural context requires `consent_given = TRUE`, public consent scope, `status = 'published'`, and a non-empty `public_summary`.
- Public well-being reports use summaries, metric observations, and aggregate language coverage only.
- Household-level observations and non-consented feedback must not appear in dashboards, reports, CIDS exports, or agent outputs.

## Governed Metrics

The module seeds these metric definitions:

- `operator_capability_score`
- `local_language_reporting_coverage`
- `community_trust_signal`
- `worker_safety_signal`
- `training_access_hours`
- `benefit_distribution_transparency`
- `cultural_capital_activity_count`

## Agent And Reports

```bash
# Public-safe well-being synthesis agent
python3 -m services.agents.wellbeing_agent --location-id UUID

# Store a draft ai_summary for human review
python3 -m services.agents.wellbeing_agent --location-id UUID --store

# Generate holistic well-being report snapshot
python3 -m services.export.report_generator --type holistic_wellbeing --location-id UUID
```

Agent outputs are drafts. They cannot verify, publish, or convert private cultural knowledge into public evidence.

## Dashboard Review

Use these dashboards before publishing community well-being claims:

- `dashboards/metabase/sql/26_holistic_wellbeing.sql`
- `dashboards/metabase/sql/27_participatory_governance.sql`

The dashboards are public-safe by construction and read from the public views above.
