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
