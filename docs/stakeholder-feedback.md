# Stakeholder Feedback

Stakeholder feedback is private by default. Public Green Paper outputs can include only consented summaries and aggregate review signals.

## Records

| Table | Purpose |
|---|---|
| `stakeholder_feedback` | Raw or summarized stakeholder feedback with consent, sentiment, themes, and maturity |
| `stakeholder_feedback_review` | Review, escalation, response, and publication trail |
| `v_public_stakeholder_feedback_summary` | Public-safe feedback summaries only |

### `stakeholder_feedback`

Feedback is scoped optionally to a location, farm, and plot. Required fields are
`feedback_type`, `stakeholder_group`, `feedback_date`, and `feedback_text`.
Records may also contain a stakeholder name, language, sentiment, themes,
suggested improvements, harms or unintended consequences, audio CID, consent
notes, public summary, evidence maturity, source lineage, metadata, and the
canonical stakeholder `party_id`/consent event added by later migrations.

`feedback_type` accepts `community_need`, `farmer_feedback`, `worker_feedback`,
`local_resident_feedback`, `buyer_feedback`, `partner_feedback`,
`advisor_feedback`, `complaint`, `consent_note`,
`harm_or_unintended_consequence`, `suggested_improvement`, or `other`.
`sentiment` accepts `positive`, `neutral`, `negative`, `mixed`, or `unknown`.
The lifecycle is `draft`, `submitted`, `verified`, `published`, or `rejected`.
Feedback is private by default with `consent_given = FALSE` and `is_public = FALSE`.

### `stakeholder_feedback_review`

Review rows retain the feedback link, reviewer, review time, action, response,
escalation level, due date, resolution time, and metadata. Allowed actions are
`acknowledged`, `needs_info`, `escalated`, `resolved`, `dismissed`, and
`published_summary`.

## Public Exposure Rules

Public feedback requires all of the following:

- `consent_given = TRUE`
- `consent_scope` is `public_summary`, `public_quote`, or `public_full`
- `is_public = TRUE`
- `status = 'published'`
- `public_summary` is non-empty
- a verified or published `farm_registry_record` for the feedback location
- an identified `party_id` with effective canonical consent for
  `stakeholder_feedback` / `public_summary`, location scope, system recipient

The database rejects public opt-in records that do not satisfy the consent,
scope, lifecycle, and summary requirements. Publishing feedback or marking it
public also requires effective canonical consent through a database trigger.
Consent can be withdrawn after publication; subsequent updates are blocked
until effective consent exists again.

The public view exposes only identifiers, location/farm IDs, feedback type,
stakeholder group, date, sentiment, themes, public summary, and evidence
maturity label. It never exposes raw `feedback_text`, audio, consent notes,
source lineage, metadata, or private review details. `public_full` consent does
not turn raw feedback into a public export.

Raw private feedback should not be included in public reports, CIDS exports,
dashboards, or agent outputs. Public feedback also has no universal maturity
threshold, although maturity and its label remain visible in the public view.

## Review Workflow

Use `draft`, `submitted`, `verified`, `published`, and `rejected` for feedback lifecycle. Rejected feedback is retained for internal governance but excluded from public dashboards and summaries.

Directus workflow transitions are role-controlled: verification is routed to
manager, supervisor, or admin roles; publication is routed to manager or admin
roles. Feedback must have a valid `submitted_at` timestamp and remain in
submitted status for at least seven days before verification. Review actions
and escalation records remain internal governance history.

Canonical consent distinguishes review use from public-summary use. A feedback
record being reviewed does not authorize quotation or publication, and approval
of a summary does not establish consent for unrelated purposes.

## Agent Synthesis

Run the feedback synthesis for one location:

```bash
python3 -m services.agents.feedback_agent --location-id LOCATION_UUID
python3 -m services.agents.feedback_agent --location-id LOCATION_UUID --store
```

`services.agents.feedback_agent` reads public rows from
`v_public_stakeholder_feedback_summary` and aggregates non-rejected feedback by
stakeholder group, feedback type, sentiment, lifecycle, consent/public state,
and evidence maturity. It reports public summaries, private/no-consent counts,
and counts of records mentioning harms or unintended consequences. Raw private
feedback is never included; private records are aggregated only.

With `--store`, it creates an `ai_summary` with `status = 'draft'`, summary type
`stakeholder_feedback`, and source tables
`stakeholder_feedback`/`stakeholder_feedback_review`. The agent cannot verify
or publish feedback or the generated summary.

## Integrations And Limitations

Feedback may support grievance cases, stakeholder outcomes, EBF evidence,
wellbeing summaries, data-stream workflows, and public cockpit counts. These
integrations do not override the feedback lifecycle, canonical consent, public
summary, registry, or human-review gates. A feedback record indicates a reported
perspective; it does not establish causation, consensus, satisfaction, or the
absence of harm.

## References And Tests

- Base schema and public view: `schemas/postgres/030_stakeholder_feedback.sql`
- Canonical consent linkage/enforcement: `schemas/postgres/228_stakeholder_consent_enforcement.sql`, `schemas/postgres/298_consent_privacy_p0.sql`
- Directus workflow and seven-day review: `extensions/kokonut-hooks/src/workflow.ts`
- Feedback hook: `extensions/kokonut-hooks/src/feedback.ts`
- Feedback agent: `services/agents/feedback_agent.py`
- Related safety: `services/agents/safety.py`
- Focused governance tests: `tests/test_stakeholder_dod_closure.py`, `tests/test_stakeholder_end_to_end.py`, `tests/test_platform_done.py`, `extensions/kokonut-hooks/src/workflow.test.ts`, and `extensions/kokonut-hooks/src/schemas.test.ts`
