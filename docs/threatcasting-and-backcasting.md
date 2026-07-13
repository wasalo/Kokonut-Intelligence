# Threatcasting and Backcasting

Kokonut's threatcasting service records plausible threats, observable warning signals, interactions, narratives, and response paths for a location. Backcasting starts from a described future state and works backward through ordered milestones. These tools support structured judgment; they do not predict the future, prove causality, authorize action, or replace human review.

The implementation is defined by `schemas/postgres/159_threatcasting.sql`, `schemas/postgres/160_backcasting_enhancements.sql`, and `services/threatcasting/`.

## Concepts

- **Threat:** A location-scoped risk with a type, potential severity, probability, velocity, reversibility, time horizon, and active flag.
- **Warning flag:** An observable indicator evaluated against configured normal, warning, and critical thresholds. A flag status is `normal`, `elevated`, `warning`, `critical`, or `unknown`.
- **Signal:** Timestamped source material that may be linked to a threat. Signals can remain unclassified and carry optional confidence, relevance, sentiment, structured data, and source references.
- **Cross-impact:** A directed relationship between two threats. Supported relationship types are `amplifies`, `attenuates`, `triggers`, `delays`, `redirects`, and `enables`.
- **Narrative:** A scenario story classified as `desirable`, `undesirable`, `baseline`, or `wildcard`. Probability and desirability are estimates, not observed facts.
- **Horizon:** A location-scoped planning interval with focus areas, review timing, and a desirability framework. Threats are linked to horizons through relevance, time-to-impact, and priority metadata.
- **Desirability assessment:** A weighted score from -1 to 1 for dimensions in GNH, 8 Forms of Capital, SDG, wellbeing, composite, or custom frameworks.
- **Cascade:** A proposed failure chain rooted in a trigger threat, with probability, severity, timing, warning, and mitigation metadata.
- **Backcast plan:** A set of rows representing ordered milestones for one narrative and location. Each milestone has its own status, target date, dependencies, responsible party, resources, and completion evidence.
- **Principle:** A desired condition linked to a narrative, optionally evaluated from a verified metric or a CRISP dimension.
- **Path comparison:** A comparison of at least two narrative routes using system heuristics and optional human scores.

## Lifecycle

Threatcasting records do not use the governed `draft` to `published` lifecycle. Their state is represented by focused fields:

- Threats, flags, horizons, principles, cross-impacts, and cascades use active or enabled booleans.
- Signals track whether classification has occurred.
- Milestones move among `pending`, `in_progress`, `completed`, `skipped`, and `blocked`.
- Assumption challenges move from `pending` to `confirmed`, `modified`, or `rejected`.
- Path comparisons store computed and manual scores but have no approval status.

A normal operating sequence is:

1. Create and scope threats for a location.
2. Add evidence-backed cross-impacts and warning flags.
3. Ingest and classify signals outside the current CLI where needed.
4. Review the threat landscape, flags, and modeled interactions.
5. Write multiple narratives, including undesirable, desirable, baseline, and wildcard cases where appropriate.
6. Assess desirability with explicit evidence and human-provided dimension scores.
7. Select a future state for planning, then create ordered backcast milestones.
8. Define measurable principles and align milestones against current governed evidence.
9. Challenge assumptions, compare paths, and obtain human approval before changing commitments or executing actions.
10. Reassess flags, metrics, CRISP values, narratives, and milestones on the horizon's review schedule.

## Commands

Run commands from the repository root. Use `python3 -m services.threatcasting --help` for the complete argument list.

### Threats, flags, and signals

```bash
python3 -m services.threatcasting create-threat --location-id UUID --name "Drought" --type climate --severity high --probability 0.7 --velocity fast --reversibility partially
python3 -m services.threatcasting list-threats --location-id UUID
python3 -m services.threatcasting get-threat --threat-id UUID

python3 -m services.threatcasting create-flag --threat-id UUID --name "Rainfall deficit" --indicator-type quantitative --threshold-critical 0.9 --threshold-warning 0.7 --threshold-normal 0.5 --unit ratio --source weather_api
python3 -m services.threatcasting evaluate-flag --flag-id UUID
python3 -m services.threatcasting flag-status --location-id UUID

python3 -m services.threatcasting ingest-signal --source weather_api --content "Rainfall 40% below normal" --threat-id UUID --signal-type text --confidence 0.8
python3 -m services.threatcasting list-signals --location-id UUID
python3 -m services.threatcasting list-signals --unclassified
```

`evaluate-flag` re-evaluates the flag's stored `current_value`; the CLI does not provide a command to set that value. An ingestion integration or direct service call to `FlagMonitor.update_flag_value()` must first supply the observation.

### Interactions, cascades, and intelligence

```bash
python3 -m services.threatcasting cross-impact --location-id UUID
python3 -m services.threatcasting simulate-interaction --threat-ids UUID1,UUID2
python3 -m services.threatcasting model-cascade --trigger-id UUID --chain UUID1,UUID2
python3 -m services.threatcasting cascade-risk --location-id UUID
python3 -m services.threatcasting intelligence --location-id UUID --days 30
python3 -m services.threatcasting briefing --location-id UUID
python3 -m services.threatcasting landscape --location-id UUID
```

Cross-impact creation and persisted cascade creation are available through the Python service classes but are not exposed as CLI commands. `model-cascade` returns a simulation; it does not persist a `threat_cascade` row.

### Narratives and horizons

```bash
python3 -m services.threatcasting create-narrative --threat-id UUID --type undesirable --title "Drought cascade" --summary "..." --story "..." --years 5 --probability 0.7 --severity high
python3 -m services.threatcasting list-narratives --location-id UUID
python3 -m services.threatcasting evaluate-narrative --narrative-id UUID --framework gnh
python3 -m services.threatcasting create-horizon --location-id UUID --name "Five year horizon" --years 5 --focus climate ecological
python3 -m services.threatcasting horizon-overview --horizon-id UUID
```

Without supplied dimension assessments at the Python API level, `evaluate-narrative` creates zero-valued placeholders and updates the narrative's overall desirability to `0.0`. The CLI therefore initializes an assessment structure; it does not independently determine desirability.

### Backcasting and principles

```bash
python3 -m services.threatcasting create-backcast --narrative-id UUID --location-id UUID --name "Drought preparedness" --future-state "..." --gaps "..." --milestones '[{"order":1,"description":"Install storage","target_date":"2027-06-30"}]'
python3 -m services.threatcasting backcast-progress --narrative-id UUID

python3 -m services.threatcasting create-principle --narrative-id UUID --location-id UUID --name "Carbon negative" --description "Net carbon sequestration" --type ecological --metric-key soil_carbon_delta --operator gte --target 0 --source-system metric
python3 -m services.threatcasting list-principles --narrative-id UUID
python3 -m services.threatcasting align-milestone --milestone-id UUID
python3 -m services.threatcasting align-all --narrative-id UUID
python3 -m services.threatcasting check-direction --plan-id UUID
python3 -m services.threatcasting gap-analysis --plan-id UUID
python3 -m services.threatcasting effectiveness --plan-id UUID
```

In the last three commands, `--plan-id` is interpreted by the implementation as a narrative ID, because a backcast is represented by multiple milestone rows rather than a separate plan header.

### Assumptions and path comparison

```bash
python3 -m services.threatcasting challenge-assumption --plan-id UUID --narrative-id UUID --original "Rainfall exceeds 800 mm" --challenged "Rainfall may fall to 600 mm" --reason "Observed decline"
python3 -m services.threatcasting list-challenges --plan-id UUID
python3 -m services.threatcasting resolve-challenge --challenge-id UUID --outcome modified --approved-by HUMAN_ID --impact "Re-sequence water milestones"

python3 -m services.threatcasting compare-paths --location-id UUID --name "Drought response options" --narrative-ids UUID1,UUID2
python3 -m services.threatcasting evaluate-paths --comparison-id UUID
python3 -m services.threatcasting manual-compare --comparison-id UUID --scores '{"UUID1":{"cost":0.8,"time":0.6},"UUID2":{"cost":0.5,"time":0.9}}'
python3 -m services.threatcasting list-comparisons --location-id UUID
python3 -m services.threatcasting premortem-create --comparison-id UUID --narrative-id UUID --failure-modes '[{"description":"Funding arrives after the planting window"}]'
python3 -m services.threatcasting premortem-submit --premortem-id UUID --submitted-by HUMAN
python3 -m services.threatcasting premortem-review --premortem-id UUID --result verified --reviewer-id UUID --notes "Reviewed failure modes and mitigations"
```

## Data Model

Schema 159 provides ten core tables:

| Table | Purpose |
| --- | --- |
| `threat` | Location-scoped threat catalog |
| `threat_flag` | Observable indicators and current threshold status |
| `threat_cross_impact` | Directed threat-to-threat effects |
| `threat_signal` | Source signals and classification metadata |
| `threat_narrative` | Scenario narratives and headline estimates |
| `threat_horizon` | Planning horizons |
| `threat_horizon_threat` | Horizon-to-threat linkage |
| `threat_desirability_assessment` | Dimension-level narrative assessments |
| `threat_backcast_plan` | One row per ordered backcast milestone |
| `threat_cascade` | Persisted cascade scenarios |

Schemas 160 and 167 add:

| Table | Purpose |
| --- | --- |
| `backcast_principle` | Desired conditions and data sources |
| `backcast_principle_alignment` | Current milestone-to-principle score snapshots |
| `backcast_assumption_challenge` | Human-resolved challenges to planning assumptions |
| `backcast_path_comparison` | Criteria, system scores, human scores, and selected winner |
| `backcast_path_premortem` | Private failure modes, assumptions, warning signals, mitigations, and human review state |

Foreign keys enforce most parent relationships. Arrays such as cascade chains, milestone dependencies, and comparison narrative IDs are UUID arrays rather than foreign-key junction tables, so the database does not validate every referenced UUID in those arrays.

Several `v_public_*` views expose active threat summaries, flag status, cross-impacts, narratives, horizons, and cascades. Unlike some other Kokonut public views, schema 159 does not gate these views on a verified or published farm registry record. Access control must therefore be enforced by the API/Directus deployment if the records are sensitive.

## Interpretation

- A probability is an entered or heuristic estimate. It is not calibrated unless operators establish and validate a calibration process.
- Cross-impact simulation combines individual probabilities as `1 - product(1 - p)` and adjusts amplification or attenuation by at most 20% of the configured impact magnitude per edge. This is described in code as Bayesian-like fusion, not formal Bayesian inference.
- Cross-impact matrix signs come from `impact_direction`; amplification-loop detection follows only edges whose `impact_type` is `amplifies`.
- Flag evaluation checks critical, then warning, then normal thresholds using the same comparison operator. Configuration order must match the indicator's direction. Non-numeric values produce `unknown`.
- Flag summary risk is a weighted status average: critical `1.0`, warning `0.6`, elevated `0.3`, and normal `0.0`.
- Cascade simulation is a deterministic heuristic over configured edges. Its cumulative value starts at `1.0`, applies edge modifiers, and is clamped to 0-1; it should not be read as an empirically estimated probability.
- Narrative desirability is the weighted mean of entered dimension scores. Zero placeholders mean “not assessed,” not neutral evidence.
- Principle alignment reads the latest verified `metric_value` for metric-backed principles, or the latest CRISP assessment for CRISP-backed principles. Missing current data or targets yields alignment `0.0`.
- Alignment values are snapshots of current evidence, not forecasts of what a milestone will cause.
- Direction is `toward` only when more than 70% of stored alignment rows are positive, `away` only when more than 70% are negative, otherwise `mixed`; no rows returns `unknown`.
- Effectiveness is evaluated only for completed milestones. Metric delta and a 90-day trend score are combined 50/50 when both exist. Association around a target date does not establish milestone causality.
- Automatic path scoring uses coarse proxies. Missing evidence remains `null`, is reported in `score_completeness`, and is excluded from the known-evidence weighted score. Cost still counts non-empty resource descriptions rather than monetary cost; time favors earlier last milestone dates; risk uses threat severity times probability.
- Manual path scoring combines each supplied criterion 50/50 with a known automatic score. An omitted manual value leaves the automatic value unchanged; a manual value can supply an otherwise unknown criterion.
- The service nominates a winner only when every configured criterion is known for every path, each path has a verified premortem, and the top score is unique. A nominated winner remains advisory and is not an approved plan.

## Human Approval Boundaries

The service computes summaries, scores, and candidate paths, but these outputs are advisory.

- Resolving an assumption challenge requires a non-empty `--approved-by` value. The field is text and the service does not itself verify the approver's identity or permissions.
- Path evaluation and manual comparison do not constitute approval and do not trigger implementation.
- Premortem verification confirms that a human reviewed failure modes and mitigations; it does not authorize path execution. Premortem details remain private and are not exposed in a public view.
- Marking milestones completed, accepting a narrative, changing operational commitments, spending funds, publishing claims, or initiating an on-chain or physical action requires the applicable human governance workflow outside this service.
- Warning and cascade states should trigger review, not automatic actuation.
- Public communication should retain uncertainty, source quality, negative findings, and dissenting interpretations.

## Privacy

Threats may contain sensitive operational vulnerabilities, source references, preparedness details, and inferred risks. Store only data appropriate to the configured access boundary. Do not place private evidence, personal data, credentials, or secret infrastructure details in narrative stories, signal content, metadata, completion evidence, or public-view fields.

The schemas do not provide field-level redaction, consent handling, or source confidentiality controls. Public views are summaries but are not anonymization mechanisms. Apply Directus roles, database privileges, and publication review deliberately.

## Limitations

- Most scores depend on manually entered probabilities, thresholds, relationships, and narratives.
- Signal ingestion does not classify, deduplicate, verify, or corroborate a signal automatically.
- The CLI does not expose every service operation, including cross-impact creation, flag-value updates, and persisted cascade creation.
- The schema does not version narratives, principles, threshold configurations, or path-comparison formulas.
- Cross-location cross-impact rows are possible at the database level; matrix output only includes edges whose endpoints occur in its location-scoped threat set.
- Array references are not fully protected by foreign keys.
- `between` is allowed in the flag schema but `FlagMonitor` does not implement a two-bound `between` threshold check.
- Desirability, cascade, and path formulas are transparent heuristics, not validated forecasting models.
- Narrative arrays are service-validated but cannot enforce element-level foreign keys; `winner_narrative_id` has a database foreign key.
- There is no built-in approval state for narratives, milestones, principles, or path comparisons.

## Operational Checklist

1. Confirm the location and responsible review group.
2. Record source, date, confidence, and uncertainty for each material claim.
3. Validate flag units, comparison direction, and threshold ordering with a domain expert.
4. Add cross-impacts only with a rationale and evidence source.
5. Maintain multiple scenarios rather than optimizing around one narrative.
6. Replace desirability placeholders with documented human assessments.
7. Use verified metrics for metric-backed principles and review CRISP recency.
8. Treat missing-data defaults and heuristic scores as uncertainty flags.
9. Require a named, authorized human to resolve assumptions and accept any plan.
10. Re-run analyses after evidence, thresholds, milestones, or formulas change and preserve review records outside mutable summary rows where auditability is required.
