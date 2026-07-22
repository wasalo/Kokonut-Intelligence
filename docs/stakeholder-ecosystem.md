# Stakeholder Ecosystem Foundation

The stakeholder foundation provides a canonical relationship layer without
replacing existing farmer, buyer, partner, cooperative, feedback, or public
records. It applies stakeholder theory by separating who a party is, how it is
identified, what relationships and interests it has, and how an advisory
salience assessment was reached.

## Core Tables

- `party`: person, organization, community, cooperative, public institution, ecosystem, species, or future-generation proxy.
- `party_identifier`: source-system identifiers and reviewable identity links.
- `party_relationship`: scoped, evidence-backed relationships between parties.
- `stakeholder_interest`: needs, claims, obligations, dependencies, benefits, harms, and stewardship interests.
- `stakeholder_salience_assessment`: power, legitimacy, urgency, vulnerability, harm exposure, and representation scores.

The compatibility view `v_stakeholder_source_candidates` exposes existing
farmer, buyer, partner, cooperative, and public records as reviewable source
candidates. It does not merge records automatically.

Identity links are additive. A candidate link never changes the source domain
record and must be reviewed before it is treated as verified.

### Foundation Constraints

`party.party_type` accepts `person`, `organization`, `community`, `cooperative`,
`public_institution`, `ecosystem`, `species`, and `future_generation`. Party
status is `draft`, `active`, `suspended`, or `retired`; privacy is `private`,
`limited`, or `public`.

`party_identifier.verification_status` is `unreviewed`, `candidate`, `verified`,
or `rejected`, with optional confidence, reviewer, review time, and evidence.
Identifiers are unique by identifier type, value, and source system.

Relationships are scoped to `network`, `organization`, `location`, `farm`,
`cooperative`, `value_stream`, `initiative`, or `decision`. Their legitimacy is
`normative`, `derivative`, `proxy`, or `unknown`; status is `proposed`, `active`,
`suspended`, `ended`, or `rejected`. Self-relationships and invalid validity
date ranges are rejected.

Interests support `need`, `claim`, `obligation`, `dependency`, `benefit`, `harm`,
and `stewardship`, with priority 1–5 and statuses `proposed`, `validated`,
`in_progress`, `met`, `deferred`, or `retired`.

Salience component scores range from 0 to 10. The generated advisory score is
weighted across power, legitimacy, urgency, vulnerability, harm exposure, and
the inverse of representation. Every assessment requires a rationale and has
`advisory`, `reviewed`, or `superseded` review status. Salience is not a
publication, consent, or exclusion decision.

## Proxy Interests

Nature and future generations are represented as explicit proxy parties. They
can have evidence-backed interests and stewardship relationships, but the
platform must not claim that a proxy party consented, voted, or spoke directly.

Salience is advisory. Low-power parties with legitimate or high-harm-exposure
interests must not be suppressed by the salience score.

## CLI

```bash
python3 -m services.analytics.cli_stakeholders create-party community "Community Name"
python3 -m services.analytics.cli_stakeholders list --party-type community
python3 -m services.analytics.cli_stakeholders landscape
python3 -m services.analytics.cli_stakeholders show PARTY_UUID
python3 -m services.analytics.cli_stakeholders identifier PARTY_UUID location_id LOCATION_UUID kokonut --status verified
python3 -m services.analytics.cli_stakeholders relationship PARTY_A PARTY_B affected_by --legitimacy normative
python3 -m services.analytics.cli_stakeholders interest PARTY_UUID need "Accessible participation"
python3 -m services.analytics.cli_stakeholders salience PARTY_UUID --legitimacy-score 9 --harm-exposure 8 --rationale "Evidence-backed affected-party assessment"
```

The internal landscape report is generated with:

```bash
python3 -m services.export.report_generator --type stakeholder_landscape --location-id LOCATION_UUID
```

The next stakeholder slices will connect this foundation to unified consent,
engagement commitments, grievance/remedy workflows, decision lineage,
representation metrics, cooperative governance, and stakeholder-aware value
streams.

## Consent

`stakeholder_consent` is an append-only canonical event stream. Grants,
withdrawals, denials, and expiries are resolved by
`v_effective_stakeholder_consent`. An absent record is always denied.

Consent events are append-only and use `grant`, `withdraw`, `deny`, or `expire`.
They carry data category, purpose, scope, recipient, method, legal basis,
version, effective/expiry times, reason, evidence, and source lineage. A reason
is required for every non-grant event. The effective view selects the latest
event for the party/data/purpose/scope/recipient tuple and marks expired grants
as expired; it does not infer consent from absence.

```bash
python3 -m services.analytics.cli_consent record PARTY_UUID social "community research" --scope-type location --scope-id LOCATION_UUID --recipient-type researcher
python3 -m services.analytics.cli_consent check PARTY_UUID social "community research" --scope-type location --scope-id LOCATION_UUID --recipient-type researcher
python3 -m services.analytics.cli_consent list --party-id PARTY_UUID
python3 -m services.analytics.cli_consent withdraw CONSENT_EVENT_UUID --reason "Purpose changed"
```

Legacy consent records are exposed through `v_mappable_legacy_consent` only
when their source identity has a verified `party_identifier` link. They are
not silently treated as canonical consent.

## Engagement

Engagement plans connect a stakeholder party to objectives, consent-aware
touchpoints, commitments, optional work items, RACI responsibility records, and
outcomes. Commitment health is advisory and exposes overdue work for existing
management escalation workflows.

Plans use `draft`, `active`, `paused`, `completed`, and `cancelled` statuses and
engagement modes `inform`, `consult`, `involve`, `collaborate`, `empower`, and
`steward`. Objectives, touchpoints, commitments, and outcomes have separate
lifecycles. A touchpoint records `consent_checked`; commitments can link to a
`work_item` and `responsibility_assignment`; overdue health is derived from due
dates and open/in-progress status.

```bash
python3 -m services.analytics.cli_stakeholder_engagement list-plans
python3 -m services.analytics.cli_stakeholder_engagement add-objective PLAN_UUID "Hear affected residents" "Community input is acknowledged"
python3 -m services.analytics.cli_stakeholder_engagement schedule-touchpoint PLAN_UUID "Discuss water stewardship" --channel-type sms --consent-checked
python3 -m services.analytics.cli_stakeholder_engagement commitment-health --overdue-only
python3 -m services.analytics.cli_stakeholder_engagement record-outcome PLAN_UUID progress "Response summary prepared"
```

The engagement report is generated with:

```bash
python3 -m services.export.report_generator --type stakeholder_engagement --location-id LOCATION_UUID
```

## Grievances and Remedies

Grievances are protected internal cases linked optionally to stakeholder
feedback. Investigations require a conflict check, evidence stays restricted
by default, remedies must be completed or explicitly rejected/waived before
closure, and undecided appeals block closure.

Cases have category, severity, confidentiality, retaliation-risk, owner,
independent-reviewer, due-date, work-item, escalation, evidence, and lifecycle
state. Investigation conflict states are `pending`, `clear`, `conflict`, or
`waived`; conflicting investigations must be cancelled. Evidence is private,
restricted, or internal. Remedies track proposal, owner, due date, affected-party
confirmation, completion evidence, and `proposed`, `accepted`, `in_progress`,
`completed`, `rejected`, or `waived` status. Closure records require a reason
and track satisfaction, complainant confirmation, and independent review.

```bash
python3 -m services.analytics.cli_stakeholder_grievances create-case representation "Input was not acknowledged" --complainant-party-id PARTY_UUID --severity high
python3 -m services.analytics.cli_stakeholder_grievances acknowledge CASE_UUID --owner-party-id OWNER_PARTY_UUID
python3 -m services.analytics.cli_stakeholder_grievances assign-investigation CASE_UUID INVESTIGATOR_PARTY_UUID "Review participation records"
python3 -m services.analytics.cli_stakeholder_grievances propose-remedy CASE_UUID explanation "Publish a response"
python3 -m services.analytics.cli_stakeholder_grievances health --overdue-only
python3 -m services.analytics.cli_stakeholder_grievances close CASE_UUID "Remedy completed" --independent-review-completed
```

The internal grievance report is generated with:

```bash
python3 -m services.export.report_generator --type stakeholder_grievance --location-id LOCATION_UUID
```

## Representation and Equity

Participation records preserve invitation denominators, attendance,
contributions, accessibility requests, and minority views. Public metrics are
suppressed for activities with fewer than five invitees. Benefit, harm, cost,
and remedy distributions require verified or published evidence before they
appear in aggregate summaries.

Public representation metrics additionally suppress an activity when any named
attendee has `consent_checked = FALSE`. Anonymous participation is permitted
when an `anonymous_group` is supplied. Minority views are preserved by default;
an unpreserved view requires a documented decision response. Distribution rows
use `draft`, `submitted`, `verified`, `published`, or `rejected` status, and the
equity summary includes only verified or published rows.

```bash
python3 -m services.analytics.cli_stakeholder_representation record-participation decision DECISION_UUID --party-id PARTY_UUID --status attended --consent-checked
python3 -m services.analytics.cli_stakeholder_representation request-accessibility PARTICIPATION_UUID language "Provide interpretation"
python3 -m services.analytics.cli_stakeholder_representation record-minority-view decision DECISION_UUID "Protect water access first" --anonymous-group "Water-dependent households"
python3 -m services.analytics.cli_stakeholder_representation metrics decision DECISION_UUID
python3 -m services.analytics.cli_stakeholder_representation distribution-summary --scope-type location --scope-id LOCATION_UUID
```

The report is generated with:

```bash
python3 -m services.export.report_generator --type stakeholder_representation --location-id LOCATION_UUID
```

## Decision Lineage

Stakeholder decisions preserve who was affected or consulted, which interests
and trade-offs were considered, what evidence supported the decision, and what
outcomes were observed. Approval is a separate human-controlled transition;
proxy parties and automated agents cannot approve decisions.

Decision statuses include `draft`, `submitted`, `approved`, `rejected`,
`in_execution`, `completed`, and `cancelled`; approval status is independently
`pending`, `approved`, or `rejected`. An approved decision must have an
`approved_by_party_id`, and the approver must be a human party where the
approval gate applies. Participants record role, participation status, consent
check, perspective, and minority view. Trade-offs explicitly classify benefit,
harm, cost, risk, or neutral direction and may carry severity and mitigation.
Evidence records include role, maturity, verification, audience, and source
lineage. Approval does not establish stakeholder consent.

```bash
python3 -m services.analytics.cli_stakeholder_decisions create "Protect minimum water access" "Choose a drought response without reducing household access." policy --created-by-party-id PARTY_UUID
python3 -m services.analytics.cli_stakeholder_decisions submit DECISION_UUID
python3 -m services.analytics.cli_stakeholder_decisions add-participant DECISION_UUID affected --party-id PARTY_UUID --status participated --consent-checked
python3 -m services.analytics.cli_stakeholder_decisions add-tradeoff DECISION_UUID harm "Potential water access impact" --severity 8 --mitigation "Protect minimum access"
python3 -m services.analytics.cli_stakeholder_decisions add-evidence DECISION_UUID metric "Verified soil moisture trend" --role supporting --maturity 4 --verified
python3 -m services.analytics.cli_stakeholder_decisions approve DECISION_UUID APPROVER_PARTY_UUID
python3 -m services.analytics.cli_stakeholder_decisions link-execution DECISION_UUID --work-item-id WORK_ITEM_UUID
python3 -m services.analytics.cli_stakeholder_decisions record-outcome DECISION_UUID harm "No material access disruption observed" --status verified
```

The internal lineage report is generated with:

```bash
python3 -m services.export.report_generator --type stakeholder_decision_lineage --location-id LOCATION_UUID
```

## Cooperative Governance and Trust

Cooperative meetings, proposals, motions, votes, quorum, delegation, conflict
declarations, and distribution decisions are recorded separately from trust
evidence. Trust profiles expose dimensions and timelines rather than a
universal reputation score. Evidence retains its source, age, confidence,
uncertainty, correction state, and appeal state.

```bash
python3 -m services.analytics.cli_stakeholder_trust record-evidence PARTY_UUID payment supporting financial_transaction "Payment settled within agreed terms" --confidence 0.9 --uncertainty 0.1
python3 -m services.analytics.cli_stakeholder_trust profile PARTY_UUID
python3 -m services.analytics.cli_stakeholder_trust timeline PARTY_UUID
python3 -m services.analytics.cli_stakeholder_trust risks --party-id PARTY_UUID
python3 -m services.analytics.cli_stakeholder_trust verify-buyer BUYER_UUID registration "Registry review" --verified-by-party-id REVIEWER_UUID
```

Trust evidence is advisory. Negative evidence supports correction and appeal,
and cannot be used as an automatic exclusion rule for financing, insurance,
market access, or participation.

## Capabilities and Value Streams

Capabilities now identify stakeholder beneficiaries, desired outcomes, demand,
criticality, access barriers, service-quality targets, satisfaction measures,
harm exposure, and dependency risk. Value streams carry stakeholder promises,
desired end states, pain points, experience measures, service-level
expectations, equity effects, feedback sources, and outcome evidence.

The underlying links are stored in `capability_stakeholder`,
`value_stream_stakeholder_outcome`, and `value_stream_feedback_source`.
Stakeholder outcomes require either a linked party or interest, and use draft,
active, verified, or retired status. These architecture links are not by
themselves proof of service quality, satisfaction, or absence of harm.

The architecture report is generated with:

```bash
python3 -m services.export.report_generator --type stakeholder_value_streams --location-id LOCATION_UUID
python3 -m services.export.report_generator --type stakeholder_outcomes --location-id LOCATION_UUID
```

## Nature and Future Generations

Ecosystem, species, and future-generation proxy parties may have explicit
stewardship obligations, ecological thresholds, principles, and decision
impacts. Proxy authority must identify its steward and basis. These records do
not claim that nature or future generations consented, voted, or spoke.

Public ecological stewardship uses a deliberate projection and preserves that
limitation. Ecological observations, model runs, forecasts, and impact claims
remain separate evidence layers.

Active proxy authority requires an identified human approver, an explicit
steward, authority basis, scope, and validity period. Public ecological
stewardship requires a public proxy party, status `approved`, `in_progress`, or
`met`, evidence maturity at least 4, and a non-empty `public_summary`. Public
projections retain an explicit limitation that proxy interests are documented
obligations, not direct speech or consent.

## Public Safety And Human Review

The internal cockpit includes active parties and relationships, open interests,
engagement and overdue commitments, open grievances, active decisions,
unresolved harms, relationship risks, pending buyer verification, contested
trust evidence, stewardship actions, and unverified value-stream outcomes.

The public cockpit is deliberately narrower. It includes public parties, public
representation summaries, verified outcomes and impact claims, verified
distributions, published consented feedback, and public ecological stewardship.
It excludes private consent, protected grievances, unresolved decision lineage,
contested trust evidence, and small-group participation. Its counts indicate
governed records; they do not prove absence of harm, satisfaction, or consent.

Human review gates require an identified human person for verified buyer records
and active proxy authority. A minority view cannot be marked unpreserved without
a documented decision response. Trust evidence is advisory and cannot become an
automatic exclusion rule for financing, insurance, market access, or
participation.

## Unified Cockpit

The internal cockpit covers landscape, relationships, salience, engagement,
consent, grievances, commitments, representation, conflicts, harms, trust,
value-stream outcomes, decisions, and stewardship risks. The public-safe
cockpit contains only aggregate governed outcomes, published feedback,
verified distributions, participation summaries, verified impact claims, and
public ecological stewardship.

```bash
python3 -m services.export.report_generator --type stakeholder_ecosystem --location-id LOCATION_UUID
python3 -m services.export.report_generator --type stakeholder_trust --location-id LOCATION_UUID
python3 -m services.export.report_generator --type stakeholder_cockpit --location-id LOCATION_UUID
```

## Report Scope And Limitations

`stakeholder_ecosystem` reads the internal cockpit, full stakeholder landscape,
relationship-risk indicators, and relationship recommendations. Its current
generator does not apply the supplied location or period filters, so it is a
network-wide internal report.

`stakeholder_trust`, `stakeholder_value_streams`, and `stakeholder_cockpit` also
read network-wide views in the current generator. `stakeholder_outcomes` filters
governed outcomes by location, but its capability/value-stream architecture
links are currently returned globally. Reports are derived projections and do
not replace canonical stakeholder records or their privacy and approval gates.

## References And Tests

- Foundation and landscape: `schemas/postgres/213_stakeholder_vocabulary.sql`
- Source candidates: `schemas/postgres/214_stakeholder_compatibility_views.sql`
- Consent: `schemas/postgres/215_stakeholder_consent.sql`, `schemas/postgres/228_stakeholder_consent_enforcement.sql`
- Engagement: `schemas/postgres/216_stakeholder_engagement.sql`, `schemas/postgres/217_stakeholder_engagement_scope_view.sql`
- Grievances: `schemas/postgres/218_stakeholder_grievances.sql`
- Representation: `schemas/postgres/219_stakeholder_representation.sql`, `schemas/postgres/220_stakeholder_representation_metrics_fix.sql`
- Decisions: `schemas/postgres/221_stakeholder_decisions.sql`, `schemas/postgres/229_stakeholder_decision_controls.sql`
- Capabilities/value streams: `schemas/postgres/223_stakeholder_capabilities_value_streams.sql`
- Nature/proxy authority: `schemas/postgres/224_nature_future_generations.sql`
- Cockpit/public safety/human review: `schemas/postgres/225_stakeholder_cockpit.sql`, `schemas/postgres/230_stakeholder_public_safety.sql`, `schemas/postgres/231_stakeholder_human_review_gates.sql`
- Reports: `services/export/report_generator.py`
- Focused tests: `tests/test_stakeholder_foundation.py`, `tests/test_stakeholder_consent.py`, `tests/test_stakeholder_engagement.py`, `tests/test_stakeholder_grievances.py`, `tests/test_stakeholder_representation.py`, `tests/test_stakeholder_decisions.py`, `tests/test_stakeholder_phases_8_11.py`, `tests/test_stakeholder_end_to_end.py`, and `tests/test_stakeholder_dod_closure.py`
