# Technology Roadmap

The technology roadmap is an advisory planning layer connecting enterprise
needs to capabilities, technology areas, measurable drivers, alternatives, and
review records. It complements the strategy map, capability map, value streams,
and portfolio; it does not replace them or authorize deployment.

Roadmap status and review records are stored in PostgreSQL. Approval and
supersession are application-level review conventions, not a complete enforced
human-authorization boundary: the service can set status directly, reviewer
identity is optional, and the roadmap tables are not in the agent safety
`GOVERNED_COLLECTIONS` set.

## Data Model

| Table | Purpose |
|---|---|
| `technology_roadmap` | Named platform, organization, or location roadmap with horizon, owner, sponsor, detail level, status, cadence, and metadata |
| `technology_roadmap_requirement` | Business, customer, operational, regulatory, or sustainability need with priority, target, status, evidence, and links |
| `technology_area` | Major technology domain within a roadmap |
| `technology_driver` | Measurable selection criterion and target linked to an area and optionally a requirement |
| `technology_alternative` | Technology option with maturity, cost, confidence, recommendation, rationale, transition link, and metadata |
| `technology_roadmap_review` | Review result, reviewer reference, notes, evidence, and timestamp |

Requirements can link directly to `strategy_map`, `business_capability`, and
`value_stream_definition`. There are no direct foreign keys to initiatives,
projects, portfolio items, or work items. `entity_id` on a roadmap is a UUID
without a polymorphic foreign-key constraint.

The roadmap hierarchy is:

```text
technology_roadmap
  -> technology_roadmap_requirement
  -> technology_area
       -> technology_driver
            -> technology_alternative
```

The portfolio view is `v_technology_roadmap_overview`. It returns roadmap
identity and scope fields, horizon, detail level, sponsor, owner, status, next
review date, requirement/area/driver/alternative counts, selected-alternative
count, and the latest review timestamp. It does not contain the full hierarchy,
evidence, or review history.

## Lifecycle And Review

The database permits these roadmap statuses:

```text
draft -> submitted -> approved -> active -> reviewed -> superseded
                              \-> rejected
```

The schema permits all listed values but does not enforce this transition graph.
`update_roadmap()` can set status directly. Review results are
`approved`, `needs_revision`, `rejected`, and `superseded`, with these resulting
statuses:

| Review result | Resulting roadmap status |
|---|---|
| `approved` | `approved` |
| `needs_revision` | `submitted` |
| `rejected` | `rejected` |
| `superseded` | `superseded` |

`needs_revision` is a review result, not a stored roadmap status. `active` and
`reviewed` are valid database values but are not produced by
`review_roadmap()`.

Review updates `next_review_at` from `review_cadence_days` when a cadence is
configured. `reviewed_by` is an optional UUID and the service does not enforce
reviewer authorization. Review evidence is supported by the service and schema,
but the CLI does not currently expose an evidence option.

## CLI

The CLI is:

```bash
python3 -m services.analytics.cli_technology_roadmap COMMAND ...
```

Create and inspect roadmaps:

```bash
python3 -m services.analytics.cli_technology_roadmap create "Platform roadmap" \
  --description "Technology choices for platform scale" \
  --entity-type platform \
  --horizon-start 2026-01-01 \
  --horizon-end 2028-12-31 \
  --detail-level portfolio \
  --sponsor "Kokonut DAO" \
  --owner "Platform team"

python3 -m services.analytics.cli_technology_roadmap list
python3 -m services.analytics.cli_technology_roadmap list --status draft --entity-type platform
python3 -m services.analytics.cli_technology_roadmap show ROADMAP_UUID
```

Add roadmap structure:

```bash
python3 -m services.analytics.cli_technology_roadmap requirement \
  ROADMAP_UUID "Reduce onboarding time" \
  --description "Shorten governed onboarding" \
  --need-type operational \
  --priority 5 \
  --target-value 30 \
  --unit days \
  --target-date 2027-01-01 \
  --capability-id CAPABILITY_UUID

python3 -m services.analytics.cli_technology_roadmap area \
  ROADMAP_UUID "Platform delivery" --order 1

python3 -m services.analytics.cli_technology_roadmap driver \
  AREA_UUID "Deployment time" \
  --requirement-id REQUIREMENT_UUID \
  --metric-key deployment_days \
  --target-value 30 --unit days --weight 8

python3 -m services.analytics.cli_technology_roadmap alternative \
  DRIVER_UUID "Reusable deployment package" \
  --maturity-status pilot \
  --estimated-cost 10000 \
  --confidence 0.8 \
  --recommendation candidate \
  --rationale "Reduces repeated delivery work"
```

Review and recommendations:

```bash
python3 -m services.analytics.cli_technology_roadmap recommend ROADMAP_UUID
python3 -m services.analytics.cli_technology_roadmap review \
  ROADMAP_UUID approved \
  --reviewed-by REVIEWER_UUID \
  --notes "Reviewed against current capability evidence"
```

The service layer has `update_roadmap()`, but no CLI update command currently
exists. The CLI also does not expose every service field, including roadmap
`entity_id`/metadata, requirement strategy-map/value-stream/evidence fields,
alternative metadata/transition fields, or review evidence.

Adding an area, driver, or alternative is an upsert by parent and name:

- Area: `(roadmap_id, name)`.
- Driver: `(area_id, name)`.
- Alternative: `(driver_id, name)`.

Repeated calls with the same name update the existing row rather than creating
a second row.

## Recommendation Semantics

`recommend ROADMAP_UUID` is read-only heuristic scoring. It loads the roadmap,
sorts alternatives, and returns each alternative's ID, name, score, stored
recommendation, driver, and maturity status. It does not:

- Change `technology_alternative.recommendation`.
- Select an alternative.
- Change roadmap lifecycle status.
- Create a deployment, initiative, or portfolio item.
- Authorize procurement or execution.

The score combines requirement priority, driver weight, alternative confidence,
and maturity. Maturity contributes the following configured values:

| Maturity | Score |
|---|---:|
| `production` | 1.0 |
| `pilot` | 0.8 |
| `available` | 0.7 |
| `emerging` | 0.4 |
| `deprecated` | 0.0 |

The result is advisory evidence for human review, not a governed decision.

## Executive Report

Generate the report with:

```bash
python3 -m services.export.report_generator \
  --type technology_roadmap \
  --location-id LOCATION_UUID
```

The generic report CLI currently requires `--location-id`, but
`generate_technology_roadmap()` ignores `location_id`, `period_start`, and
`period_end` and returns all roadmaps. Treat this as a platform/network-wide
report; location and period filters currently have no effect.

The report includes roadmap overview rows, selected requirement fields, and
alternative summaries. It does not currently include full roadmap metadata,
strategy/capability/value-stream link IDs, requirement evidence, review history,
technology areas or drivers as separate structured sections, alternative
rationale/metadata, or transition links. Use `show ROADMAP_UUID` for the full
roadmap hierarchy.

## Seed And Operations

The seeded platform example is `Kokonut Platform Scale Roadmap`. Its expected
overview structure is three requirements, three technology areas, three
drivers, and three alternatives.

Roadmap recommendations and reports are advisory. Link roadmap requirements to
the available strategy-map, capability, and value-stream records before
authorizing execution through the appropriate planning and governance flows.
Do not treat a roadmap status or alternative recommendation as proof of
technical validation, financial approval, procurement approval, or deployment.

## References And Tests

- Service: `services/analytics/technology_roadmap.py`
- CLI: `services/analytics/cli_technology_roadmap.py`
- Schema and overview view: `schemas/postgres/212_technology_roadmap.sql`
- Report: `services/export/report_generator.py`
- Agent safety boundary: `services/agents/safety.py`
- Focused tests: `tests/test_technology_roadmap.py`

Current tests cover lifecycle creation, hierarchy/detail retrieval, heuristic
recommendations, seeded overview counts, and report presence. They do not fully
cover CLI argument behavior, reviewer authorization, invalid transitions,
review evidence, report filter scope, or all relationship fields.
