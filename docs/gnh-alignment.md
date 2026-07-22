# GNH Alignment And Inclusion

Kokonut records Gross National Happiness (GNH) alignment as governed,
reviewer-assessed evidence. The module combines domain alignment, cultural
preservation, renewable-energy planning, vulnerable-group access, and
foundational wellbeing observations.

These records describe evidence from a location. They do not certify national
happiness, Bhutan readiness, cultural equivalence, clinical wellbeing, or
completed inclusion outcomes. Stronger claims require local review, appropriate
evidence, consent, and the relevant governed lifecycle state.

## Evidence Model

The GNH module uses five governed record types:

| Table | Purpose | Primary date/domain fields |
|---|---|---|
| `gnh_alignment_assessment` | Reviewer-assessed alignment by GNH domain, including strengths, gaps, safeguards, and public summary | `assessment_date`, `gnh_domain`, `alignment_score` |
| `cultural_preservation_plan` | Cultural preservation, local-language access, consent, digital integration, and local-review planning | `plan_date`, `cultural_element`, `preservation_type` |
| `renewable_energy_plan` | Planned or implemented renewable infrastructure and conservative energy/displacement estimates | `plan_date`, `energy_use_case`, `renewable_source` |
| `vulnerable_group_access_plan` | Group-level barriers, accommodations, participation pathways, and accountability | `plan_date`, `access_scope`, `access_coverage_pct` |
| `foundational_wellbeing_observation` | Public-safe happiness, peace, safety, food security, basic-needs, dignity, and belonging signals | `observation_date`, `wellbeing_domain`, `score_value`/`count_value` |

Every record is tied to a `location_id`. Optional `farm_id`, source metadata,
raw source payloads, creator fields, and `metadata` support provenance without
making private source material public.

## Lifecycle And Evidence

All five tables use the governed lifecycle vocabulary:

```text
draft -> submitted -> verified -> published
                         \-> rejected
```

Only published rows with sufficient evidence maturity and a non-empty public
summary are eligible for the public views described below. Agents may create
draft outputs where explicitly allowed, but cannot verify or publish governed
records.

The public views require all of the following:

1. Source record `status = 'published'`.
2. `evidence_maturity >= 3`.
3. A non-empty, non-whitespace `public_summary`.
4. A related `farm_registry_record` for the location with status `verified` or
   `published`.

Evidence maturity is a publication gate, not proof that a claim is complete or
externally certified. Public summaries must remain privacy-safe and must state
whether evidence is planned, implemented, inferred, or otherwise limited.

## GNH Domains

### Stored Assessment Domains

`gnh_alignment_assessment.gnh_domain` is constrained to:

- `psychological_wellbeing`
- `health`
- `education`
- `culture`
- `time_use`
- `good_governance`
- `community_vitality`
- `ecological_diversity`
- `living_standards`
- `other`

`alignment_score` is optional and, when present, must be between `0` and `10`.
Assessments also store `principle_refs`, `strengths`, `gaps`, `safeguards`, an
internal `assessment_summary`, and an optional `public_summary`.

### Threatcasting GNH Framework

Threatcasting uses a separate nine-dimension weighted framework for desirability
assessment. It is configured in `services/threatcasting/config.py` and includes:

| Dimension | Weight |
|---|---:|
| `psychological_wellbeing` | 0.15 |
| `community_vitality` | 0.12 |
| `culture` | 0.10 |
| `time_use` | 0.08 |
| `education` | 0.10 |
| `health` | 0.12 |
| `good_governance` | 0.10 |
| `ecological_diversity` | 0.13 |
| `living_standards` | 0.10 |

This framework is used for threat narrative desirability and is not a second
public-record table. Do not imply that its weighted score is the same as the
stored `gnh_alignment_score` metric.

## Cultural Preservation

`cultural_preservation_plan` supports these preservation types:

- `traditional_practice`
- `local_language`
- `heritage_species`
- `storytelling`
- `cultural_review`
- `visual_identity`
- `education`
- `other`

The record can identify a `local_language`, summarize traditional practice,
describe a digital integration strategy, specify a consent protocol, and name a
cultural-context evidence model.

Implementation status is one of:

```text
planned, in_progress, implemented, blocked, deferred, cancelled
```

Public cultural records expose summaries and review metadata only. Private
cultural knowledge, raw stories, and non-consented material must remain outside
public output. A plan with `implementation_status = 'planned'` is not an
implemented preservation outcome.

## Renewable Energy

`renewable_energy_plan` supports these renewable sources:

```text
solar, biogas, wind, micro_hydro, biomass, renewable_grid, hybrid, other
```

The record distinguishes:

- `implementation_status`: planned, in progress, implemented, blocked,
  deferred, or cancelled;
- `current_energy_source`;
- `planned_capacity_kw`;
- `estimated_annual_kwh`;
- `renewable_share_pct`;
- `fossil_displacement_estimate_co2e_tonnes`;
- infrastructure dependencies;
- maintenance owner role.

Capacity, annual energy, and displacement estimates must be non-negative.
`renewable_share_pct` must be between `0` and `100`.

Planning estimates are not operational measurements. Fossil displacement is a
conservative planning signal, not a carbon-credit claim. Implemented renewable
share claims require follow-up operational energy evidence and should not be
presented as implemented merely because a plan is published.

## Vulnerable-Group Access

`vulnerable_group_access_plan` supports these access scopes:

- `farm_operations`
- `governance`
- `reporting`
- `training`
- `benefit_distribution`
- `digital_access`
- `other`

Records use group-level fields for:

- `vulnerable_groups`;
- `access_barriers`;
- `accommodations`;
- `participation_pathways`;
- `accountable_role`;
- `implementation_status`;
- `access_coverage_pct`.

`access_coverage_pct`, when present, must be between `0` and `100`. A published
plan is evidence that an access pathway or accommodation has been documented;
it is not proof that all affected people can access or benefit from it.

Do not publish raw disability, household, protected-class, identity, or
individual participation data. Use privacy-safe group summaries and consult
affected groups before making stronger inclusion claims.

## Foundational Wellbeing

`foundational_wellbeing_observation` supports these wellbeing domains:

```text
happiness, peace, safety, food_security, basic_needs, dignity, belonging, other
```

An observation may use a normalized `score_value` from `0` to `10`, a non-negative
`count_value`, or a qualitative signal. At least one of these must be present.
The record may identify a broad `stakeholder_group` and list source tables, but
public output should not expose raw private feedback or household-level detail.

These observations are public-safe evidence signals. They are not clinical
assessments, external certifications, or claims that a community has achieved a
particular wellbeing level. Unresolved allegations and unreviewed harm claims
must not be promoted into public wellbeing evidence.

## Public Views

The schema defines five public views. Each applies the same lifecycle, evidence,
summary, and registry gates described above.

| View | Public content |
|---|---|
| `v_public_gnh_alignment_summary` | Domain, score, principle references, strengths, gaps, safeguards, summary, maturity |
| `v_public_cultural_preservation_summary` | Cultural element, preservation type, language, integration strategy, consent protocol, reviewer role, implementation state, summary |
| `v_public_renewable_energy_summary` | Energy use case, source, implementation state, capacity, annual kWh, share, displacement estimate, dependencies, maintenance role, summary |
| `v_public_vulnerable_access_summary` | Access scope, group-level barriers, accommodations, pathways, accountable role, implementation state, coverage, summary |
| `v_public_foundational_wellbeing_summary` | Wellbeing domain, broad stakeholder group, score/count, maturity, summary |

The views join `evidence_maturity_level` to provide
`evidence_maturity_label`. They do not expose the internal assessment summary,
raw source payload, or unrestricted private evidence.

## Governed Metrics

The metric seed defines these active metrics:

| Metric | Meaning | Unit/frequency |
|---|---|---|
| `gnh_alignment_score` | Reviewer-normalized domain alignment score | `score_0_10`, quarterly |
| `cultural_preservation_activity_count` | Published cultural plans or implemented integration activities | count, quarterly |
| `local_language_access_coverage_pct` | Local-language workflow coverage | percentage, monthly |
| `renewable_energy_share_pct` | Renewable share from published energy plans | percentage, quarterly |
| `fossil_energy_displacement_estimate` | Conservative estimated annual fossil displacement | `tCO2e`, quarterly |
| `vulnerable_group_access_coverage_pct` | Addressed barriers relative to identified barriers | percentage, quarterly |
| `foundational_wellbeing_score` | Reviewer-normalized public-safe wellbeing signal | `score_0_10`, quarterly |
| `peace_and_safety_signal` | Reviewed peace, safety, and peaceful-participation signal | `score_0_10`, quarterly |

Metric inclusion rules require published or consent-safe evidence and preserve
the distinction between plans, implemented records, inferred signals, and
verified claims. Metric computation creates draft, unverified `metric_value`
rows; it is not a verification step.

## Reports

Generate the five report types for a location:

```bash
python3 -m services.export.report_generator --type gnh_alignment --location-id UUID
python3 -m services.export.report_generator --type cultural_preservation --location-id UUID
python3 -m services.export.report_generator --type renewable_energy --location-id UUID
python3 -m services.export.report_generator --type vulnerable_access --location-id UUID
python3 -m services.export.report_generator --type foundational_wellbeing --location-id UUID
```

All five reports accept optional date filters:

```bash
python3 -m services.export.report_generator \
  --type gnh_alignment \
  --location-id UUID \
  --period-start 2026-01-01 \
  --period-end 2026-12-31
```

Report outputs are location-scoped and read from the public views. They include
`report_type`, `location_id`, `location_name`, serialized records, limitations,
and `generated_at`.

Report-specific fields include:

- `gnh_alignment`: `assessments` and `average_alignment_score`;
- `cultural_preservation`: `plans`;
- `renewable_energy`: `plans`, `planned_count`, and `implemented_count`;
- `vulnerable_access`: `plans`;
- `foundational_wellbeing`: `observations`.

The reports explicitly state that GNH alignment is not Bhutan-readiness
certification, local cultural review is required for cross-cultural adaptation,
renewable displacement is not a carbon-credit claim, planned accommodations are
not completed inclusion outcomes, and wellbeing signals are not clinical or
external certification.

## Dashboards

The seed registers five published dashboard datasets with a 1,440-minute
refresh interval and public-safe metadata:

| Dataset | SQL | Dashboard |
|---|---|---|
| GNH Alignment Summary | `dashboards/metabase/sql/39_gnh_alignment.sql` | `dashboards/metabase/39_gnh_alignment.json` |
| Cultural Preservation Summary | `dashboards/metabase/sql/40_cultural_preservation.sql` | `dashboards/metabase/40_cultural_preservation.json` |
| Renewable Energy Summary | `dashboards/metabase/sql/41_renewable_energy.sql` | `dashboards/metabase/41_renewable_energy.json` |
| Vulnerable Access Summary | `dashboards/metabase/sql/42_vulnerable_access.sql` | `dashboards/metabase/42_vulnerable_access.json` |
| Foundational Wellbeing Summary | `dashboards/metabase/sql/43_foundational_wellbeing.sql` | `dashboards/metabase/43_foundational_wellbeing.json` |

The SQL queries read the public views and join `location` for display names.
Dashboard visibility must not be used to bypass the public-view filters.

## GNH Synthesis Agent

Run the public-safe synthesis agent with:

```bash
python3 -m services.agents.gnh_agent --location-id UUID
```

Omit `--location-id` to summarize all locations visible through the public
views. To persist the generated narrative as a draft `ai_summary`:

```bash
python3 -m services.agents.gnh_agent --location-id UUID --store
```

The agent reads only:

- `v_public_gnh_alignment_summary`;
- `v_public_cultural_preservation_summary`;
- `v_public_renewable_energy_summary`;
- `v_public_vulnerable_access_summary`;
- `v_public_foundational_wellbeing_summary`.

Its summary includes:

- `gnh_alignment_count`;
- `cultural_preservation_count`;
- `renewable_energy_count`;
- `vulnerable_access_count`;
- `foundational_wellbeing_count`;
- `average_alignment_score` when scores exist;
- `implemented_renewable_count`;
- `planned_renewable_count`;
- the five source-record arrays;
- a synthesized narrative;
- a safety note.

The agent distinguishes planned and implemented renewable records in its
narrative. It excludes private cultural knowledge, raw vulnerable-group
identity data, Bhutan-readiness claims, and implemented renewable claims without
evidence.

The catalogue entry is `gnh_alignment_synthesis`:

- risk: medium;
- optional input: `location_id`;
- optional input: `store`;
- required output: `summary` object;
- optional output: `ai_summary_id` UUID;
- permitted write: `ai_summary:draft` only;
- high risk: false.

Stored summaries remain drafts for human review. The agent cannot publish,
verify, attest, or autonomously change the source records.

## Adelphi Pilot Boundaries

The pilot seed contains public examples for the Adelphi location, including:

- ecological-diversity, culture, and community-vitality assessments;
- Spanish-language and local-practice preservation planning;
- a planned solar pathway for irrigation and sensor support;
- planned accommodations for local-language, disabled, privacy-sensitive, and
  non-wallet participants;
- dignity and peace observations.

The pilot records intentionally preserve these boundaries:

- renewable energy is `planned`, not implemented;
- fossil displacement is an estimate, not a carbon-credit claim;
- access coverage and accommodations are planning evidence, not complete
  inclusion outcomes;
- cultural summaries require consent and local reviewer participation;
- only group-level vulnerable-access data is public;
- no Bhutan-specific readiness claim is made;
- unsupported identities or farm claims are excluded from the seed.

## Related Threatcasting Use

Threatcasting can assess future narratives with `framework = 'gnh'` or the
default `gnh_aligned` desirability framing. This is advisory scenario analysis,
not a substitute for the governed GNH assessment records or their publication
gates.

Use the threatcasting CLI for narrative assessment rather than treating a
scenario score as a published GNH metric:

```bash
python3 -m services.threatcasting --help
```

All threatcasting outputs remain advisory and subject to the broader human
review boundaries in the threatcasting documentation.

## Security And Privacy Rules

1. Keep lifecycle state separate from implementation, payment, attestation, or
   domain state.
2. Do not expose private cultural knowledge, raw feedback, household details,
   or individual protected-class information.
3. Use public summaries only after consent, evidence maturity, publication, and
   registry eligibility requirements are met.
4. Distinguish planned, in-progress, implemented, blocked, deferred, and
   cancelled states in reports and dashboards.
5. Treat GNH scores as reviewer-assessed evidence signals, not universal or
   external certifications.
6. Require local review before transferring cultural or Bhutan-specific claims
   to another context.
7. Do not convert renewable-energy estimates into carbon-credit claims without
   the separate credit, methodology, and verification controls.
8. Treat agent output as draft-only and require human review before publication.

## Commands And References

Primary commands:

```bash
python3 -m services.export.report_generator --type gnh_alignment --location-id UUID
python3 -m services.export.report_generator --type cultural_preservation --location-id UUID
python3 -m services.export.report_generator --type renewable_energy --location-id UUID
python3 -m services.export.report_generator --type vulnerable_access --location-id UUID
python3 -m services.export.report_generator --type foundational_wellbeing --location-id UUID
python3 -m services.agents.gnh_agent --location-id UUID [--store]
```

Implementation references:

- `schemas/postgres/038_gnh_alignment_and_inclusion.sql`
- `schemas/seeds/039_gnh_alignment_and_inclusion.sql`
- `schemas/seeds/039_pilot_gnh_alignment.sql`
- `services/export/report_generator.py`
- `services/agents/gnh_agent.py`
- `services/agents/tasks.py`
- `services/threatcasting/config.py`
- `dashboards/metabase/sql/39_gnh_alignment.sql`
- `dashboards/metabase/sql/40_cultural_preservation.sql`
- `dashboards/metabase/sql/41_renewable_energy.sql`
- `dashboards/metabase/sql/42_vulnerable_access.sql`
- `dashboards/metabase/sql/43_foundational_wellbeing.sql`

Tests:

- `tests/test_gnh_alignment.py`
- `tests/test_holistic_wellbeing.py`
- `tests/test_state_of_kokonut.py`
