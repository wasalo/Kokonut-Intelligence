# Real-time Delphi

Kokonut's Delphi service supports structured, roundless consultation. Panel members can revise one score and rationale per item while a study is open; each submission updates aggregate statistics and appends a consensus-history snapshot. A facilitator can summarize the panel and draft a recommendation, but only a human may approve that recommendation.

The implementation is defined by `schemas/postgres/161_delphi.sql`, `services/delphi/`, and `services/agents/delphi_facilitator_agent.py`.

## Concepts

- **Study:** A consultation with a variation, facilitator type, stopping criteria, and `draft`, `open`, or `closed` status.
- **Panel member:** A participant reference represented in outputs by a display token, role, anonymity flag, and expert weight.
- **Item:** An `issue`, `goal`, or `option` scored on desirability, technical feasibility, political feasibility, or probability over a configured numeric range.
- **Contribution:** A member's current score and optional reasoning for one item. Resubmission updates the existing row rather than adding a second current answer.
- **Consensus snapshot:** The current median, mean, interquartile range (IQR), population standard deviation, coefficient of variation (CV), participant count, weighted median, and consensus flag for an item.
- **Consensus history:** An append-only snapshot created after each contribution update and used for inter-submission stability checks.
- **Recommendation:** Facilitator-authored text with `draft`, `approved`, or `rejected` status. The current service exposes draft and approval operations, but no rejection command.

Real-time Delphi is “roundless” because contributions can be revised continuously while the study is open. It is not a chat system, voting system, or automatic policy decision.

## Lifecycle

1. Create a study. It starts as `draft`.
2. Define the question, stopping criteria, scale semantics, and facilitation mode.
3. Add panel members and items.
4. Open the study. The service records `opened_at`.
5. Collect contributions. Each member may hold one current contribution per item.
6. Review anonymized live summaries, disagreement, sample size, and stopping indicators.
7. Continue recruitment or elicitation when participation or stability is inadequate.
8. Draft a recommendation only after reviewing the evidence and dissent.
9. Have an authorized human approve, revise, or reject the draft through the applicable governance process.
10. Close the study explicitly. A stopping result does not close it automatically.

`open-study` and `close-study` update status directly. The implementation does not enforce a one-way transition graph, minimum panel size before opening, complete participation before closing, or an approved recommendation before closing.

## Commands

Run commands from the repository root. Use `python3 -m services.delphi --help` for all arguments.

### Create and configure

```bash
python3 -m services.delphi create-study --title "Drought response priorities" --location-id UUID --variation real_time --facilitator-type hybrid --criteria '{"max_duration_hours":720,"stability_pct":5.0,"min_participants":3,"iqr_threshold":0.2}' --created-by HUMAN_UUID
python3 -m services.delphi list-studies
python3 -m services.delphi add-panel --study-id UUID --ref-type farmer_identity --ref-id UUID --role expert
python3 -m services.delphi add-item --study-id UUID --label "Adopt drought-tolerant crops" --type option --scale feasibility_technical --min-value 0 --max-value 1
python3 -m services.delphi open-study --study-id UUID
```

Supported study variations are `classic`, `policy`, `argument`, `disaggregative`, `real_time`, and `fast_track`. They are stored as metadata; the service currently uses the same contribution and aggregation workflow for all variations.

Supported participant reference types are `farmer_identity`, `stakeholder_group`, `guild_contributor`, and `agent`. The CLI does not constrain `--ref-type`, but the database does.

`list-studies` takes no arguments and returns the newest 50 studies. `add-panel`
also accepts `--token`, `--public` (which disables anonymity), and explicit
`--weight`. The default panel-member weight created by the service is `1.0`.

### Participate and monitor

```bash
python3 -m services.delphi submit --study-id UUID --item-id UUID --member-id UUID --score 0.8 --reasoning "Locally available seed varieties"
python3 -m services.delphi live-summary --study-id UUID
python3 -m services.delphi consensus --study-id UUID
python3 -m services.delphi check-stopping --study-id UUID
python3 -m services.delphi list-panel --study-id UUID
```

Submissions are accepted only when the item and panel member belong to the study, the study is `open`, and the score is within the item's configured range.

### Facilitate and approve

```bash
python3 -m services.agents.delphi_facilitator_agent --study-id UUID
python3 -m services.agents.delphi_facilitator_agent --study-id UUID --draft --recommendation-text "Proceed to human review of the two highest-consensus options."

python3 -m services.delphi draft-recommendation --study-id UUID --text "Proceed to human review..." --summary "..." --created-by UUID
python3 -m services.delphi list-recommendations --study-id UUID
python3 -m services.delphi approve-recommendation --recommendation-id UUID --approved-by HUMAN_UUID
python3 -m services.delphi close-study --study-id UUID
```

If the agent is run with `--draft` and no custom text, it drafts a generic recommendation to close the study and adopt median positions. That text is only a draft and must be critically reviewed; the agent does not first require that stopping criteria have been met.

There are no core Delphi CLI commands for diversity targets or assessments,
minority reports, persisted stopping evaluations, probability forecasts, or
expert calibration. Those capabilities are represented in migration 170 and
adjacent services rather than the `services.delphi` command surface.

## Data Model

| Table | Purpose |
| --- | --- |
| `delphi_study` | Study configuration, status, timing, and stopping criteria |
| `delphi_panel_member` | Participant linkage, display token, role, and weight |
| `delphi_item` | Questionnaire item and numeric scale |
| `delphi_contribution` | Current member response per item |
| `delphi_consensus` | Current aggregate snapshot per item |
| `delphi_consensus_history` | Append-only aggregate history |
| `delphi_recommendation` | Draft and human-reviewed recommendations |

`v_delphi_study_summary` reports panel, item, and open-draft counts. `v_delphi_item_live` joins item definitions to current consensus. `v_delphi_consensus_public` exposes only aggregate fields and only when all of these conditions hold:

- The study is `closed`.
- At least one recommendation for the study is `approved`.
- The study's location has a `verified` or `published` `farm_registry_record`.

A study without a location cannot satisfy the registry condition and therefore does not appear in `v_delphi_consensus_public`.

### Extended Delphi Tables

Migration `schemas/postgres/170_delphi_threat_resolution.sql` extends the core
consultation model:

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `delphi_diversity_target` | Representation target for a study | dimension_key, category_code, minimum_count, minimum_share |
| `delphi_diversity_assessment` | Assessment of panel representation | panel_size, participating_size, target_results, diversity_status |
| `delphi_stopping_evaluation` | Persisted stopping-evaluation schema | outcome, consensus, participation, stability, duration, detail |
| `delphi_minority_report` | Dissent position and review trail | title, position_summary, rationale, evidence_refs, status |
| `delphi_expert_calibration` | Forecast calibration result | panel_member_id, domain_key, brier_score, calibrated_weight |
| `threat_forecast_question` | Forecast question linked to a threat | threat_id, domain, question, resolution_criteria, status |
| `threat_probability_forecast` | Probability forecast submission | question_id, probability, source_type, methodology_version |
| `threat_forecast_resolution` | Resolved forecast outcome | question_id, outcome, evidence, resolved_by |
| `threat_forecast_score` | Forecast scoring result | question_id, forecast_id, brier_score |

The migration also adds `stakeholder_group`, `geography_code`,
`affected_community`, `lived_experience`, `expertise_domains`,
`conflict_disclosure`, and `consent_status` to `delphi_panel_member`.
`consent_status` is `pending`, `granted`, or `withdrawn`. Withdrawn members are
excluded from diversity participation counts, but the underlying identity
reference remains available to authorized database users.

The current Delphi service does not persist rows to
`delphi_stopping_evaluation`, and there is no Delphi CLI command for configuring
diversity targets, assessing diversity, creating or reviewing minority reports,
or running expert calibration. These are schema and adjacent-service
capabilities, not part of the core CLI surface.

### Core Constraints And Defaults

| Object | Important constraints or defaults |
|--------|------------------------------------|
| `delphi_study` | `variation` is `classic`, `policy`, `argument`, `disaggregative`, `real_time`, or `fast_track`; status is `draft`, `open`, or `closed`; facilitator type is `agent`, `human`, or `hybrid` |
| `delphi_panel_member` | Reference type is `farmer_identity`, `stakeholder_group`, `guild_contributor`, or `agent`; role is `expert`, `policymaker`, or `citizen`; weight is non-negative; display token is unique per study |
| `delphi_item` | Type is `issue`, `goal`, or `option`; scale is `desirability`, `feasibility_technical`, `feasibility_political`, or `probability`; `min_value < max_value`; default range is `-1.0` to `1.0` |
| `delphi_contribution` | One current row per `(item_id, panel_member_id)`; score range is enforced by the service, not by a database check |
| `delphi_consensus` | One current row per item; stores ordinary and weighted aggregates plus `consensus_reached` |
| `delphi_recommendation` | Status is `draft`, `approved`, or `rejected`; approval metadata is required by the approval operation, not fully authenticated by the service |

Pydantic models provide defaults such as `real_time`, `draft`, facilitator
`agent`, item type `option`, desirability scale, and `-1.0` to `1.0` values.
The CLI/service persistence path does not use those models as a substitute for
database or service validation.

### Diversity Assessment

`PanelManager.assess_diversity()` groups participating members by role,
stakeholder group, geography, affected-community status, and lived experience.
It compares those groups to configured targets and persists a
`delphi_diversity_assessment` with one of:

- `not_configured`
- `insufficient_data`
- `targets_met`
- `targets_partially_met`
- `targets_not_met`

The assessment is a representation diagnostic, not a proof that a panel is
fair or representative. Target definitions and participation counts should be
reviewed by a human facilitator.

### Minority Reports

`MinorityReportManager` provides a separate dissent workflow:

```text
draft → submitted → verified
                  ↘ rejected
```

Reports can link to a study, item, and panel member and include a title,
position summary, rationale, evidence references, and implications. Review
requires a reviewer UUID and nonblank review notes. There is currently no
Delphi CLI command for this workflow.

## Consensus Interpretation

- The median and IQR are the primary robust location and dispersion statistics.
- IQR uses linearly interpolated 25th and 75th percentiles and is unavailable for fewer than two scores.
- Standard deviation is the population standard deviation.
- CV is `standard deviation / abs(mean)` and is unavailable when the mean is zero or effectively zero. It is especially hard to interpret on scales spanning negative and positive values.
- The weighted median uses `expert_weight`; the ordinary median, mean, IQR, standard deviation, CV, consensus flag, and stopping stability do not use weights.
- A zero or negative total weight causes weighted median to fall back to the ordinary median. The schema itself permits zero weights but not negative weights.
- Per-item consensus is reached when participant count meets `min_participants` and IQR is at or below `iqr_threshold`.
- The default stopping criteria are 720 maximum hours, 5% IQR stability, three participants, and IQR at most `1.0`. An IQR threshold is meaningful only relative to the configured item scale.
- Stability is the percentage change in IQR between the current and immediately previous submission snapshots, and it also requires median movement to be at or below `median_shift_threshold` (default: `iqr_threshold * 0.1`). It does not measure elapsed time between observations, participant turnover, or stability across several observations.
- An item advises stopping when any one condition holds: consensus, stable IQR with enough participants, or maximum duration exceeded.
- A study advises stopping only when every item with a consensus snapshot advises stopping. A study with no snapshots returns `should_stop: false`.
- Duration can trigger stopping without minimum participation. This means “time limit reached,” not “consensus reached.”
- `check-stopping` is advisory and does not mutate study status.

Automatically derived expert weights currently default to `1.0` for every panel member. The CLI accepts an explicit `--weight`, constrained by the model to `0` through `10`. The separate threat-forecast calibration service can calculate a post-hoc weight between `0.5` and `1.5` and persist it in `delphi_expert_calibration`, but it does not automatically update live panel-member weights. Any weighting policy should be disclosed and reviewed for legitimacy and bias.

## Facilitator Agent

The facilitator agent performs two operations:

- It calls `get_live_summary()` and produces a textual synthesis of aggregate item statistics and the lowest/highest scoring viewpoints. The generated synthesis does not include the stored reasoning text, although the returned `conflicting_viewpoints` data still contains it.
- Optionally, it creates a `delphi_recommendation` with status `draft` after checking the agent safety rule for draft creation and validating its output shape.

The agent does not run an LLM in this module, independently evaluate source evidence, test stopping criteria before drafting, close studies, approve recommendations, publish results, or execute downstream actions. Its synthesis is templated from stored values.

## Human Approval Boundaries

- Agents may summarize and create draft recommendations only.
- `approve-recommendation` requires `approved_by` and only updates a recommendation currently in `draft` status.
- Approval also requires at least one persisted `delphi_diversity_assessment` for the study and no minority report in `draft` or `submitted` status.
- The service checks that `approved_by` is non-empty, but does not itself authenticate the UUID, confirm a role, or verify authorization. The calling API and governance process must do that.
- Approval changes recommendation state; it does not implement the recommendation, close the study, spend funds, publish a narrative, or authorize on-chain or physical action.
- Approval does not require the diversity status to be `targets_met`, a closed study, a completed stopping evaluation, or consensus on every item.
- Operators should not approve a recommendation solely because `consensus_reached` or `should_stop` is true. Review participation, scale design, dissent, conflicts of interest, evidence quality, and affected-community representation.
- Public aggregate eligibility in the database view is a release gate, not evidence that consultation was fair or representative.

## Reporting And Integrations

The report generator reads `v_delphi_consensus_public` for a location and
surfaces consultation dissent in the public-interest context:

- `delphi_dissent` includes the count of non-consensus items and maximum IQR.
- `DELPHI_NON_CONSENSUS` is emitted as a finding when public consensus data
  contains unresolved disagreement.
- Public reporting should preserve anonymized minority views and disclose
  non-consensus rather than presenting a median as unanimous agreement.

The report path uses the public view's gates: closed study, approved
recommendation, and verified or published location registry. It does not expose
panel reasoning or display tokens through that view.

There is no Delphi-specific workflow specification under
`services/workflow_specs/`, and no Delphi projection in
`services/graph_projection/`. A `delphi_study` stakeholder activity type exists,
but that enum value is not a generated Delphi process model.

Threat forecasting provides a separate integration. Forecast questions and
probability forecasts can link to Delphi items, and the calibration service can
compute Brier scores and persist `delphi_expert_calibration`. Calibration is
post-hoc and does not automatically alter live Delphi panel weights.

## Privacy and Pseudonymity

The system provides pseudonymity in selected outputs, not guaranteed anonymity.

- Each member has a `display_token`; a random token is generated when none is supplied.
- `list-panel` omits `participant_ref_type` and `participant_ref_id`, but returns member IDs, tokens, roles, weights, anonymity flags, and join times.
- The live summary exposes the display token, score, and full reasoning for the lowest and highest contribution on each item.
- The underlying panel table may retain `participant_ref_id`, which can link a token to a person or organization for users with database access.
- `is_anonymous` records intent but does not alter the live-summary query. The live summary always uses display tokens.
- Stable tokens, distinctive reasoning, small panels, roles, timestamps, scores, and external knowledge can enable re-identification.
- The public consensus view contains aggregate statistics only and does not expose reasoning or tokens.

Operational privacy controls should include restricted table access, minimum reporting cell sizes, review or redaction of free-text reasoning, purpose limitation, retention rules, participant notice, and consent where applicable. Do not promise anonymity when identity linkage is retained.

## Limitations

- A contribution update overwrites the prior score and reasoning. Consensus history preserves aggregate snapshots, not the member's response history.
- Consensus history is append-only by convention; the schema does not enforce immutability.
- `check-stopping` returns an in-memory result; although migration 170 defines `delphi_stopping_evaluation`, the current service does not persist evaluations there.
- The database does not constrain a contribution's score to the item's range; range validation occurs in the service method and can be bypassed by direct writes.
- The schema does not enforce that `study_id`, `item_id`, and `panel_member_id` all refer to the same study; the service method performs those checks.
- Opening, closing, adding members, and adding items have limited lifecycle guards. Items and panel members can be added regardless of study status through current service methods.
- The service has no invitation, authentication, conflict-of-interest, quorum, withdrawal, consent, or participant-notification workflow.
- The service does not detect coordinated responses, duplicate real-world participants, strategic scoring, or unrepresentative sampling.
- IQR stability between two adjacent submissions can be reached prematurely, especially with small panels or unchanged dispersion.
- Extreme-view summaries select only the lowest and highest scores. They are not a complete qualitative synthesis and may expose identifiable reasoning.
- The public view requires an approved recommendation but does not require every item to have reached consensus.
- Recommendation rejection exists in the schema but is not implemented by the CLI or `Facilitator` service. Minority reports do have a separate submitted/verified/rejected workflow.
- Study variation and facilitator type are descriptive configuration; they do not currently select distinct algorithms.
- Automatically derived panel weights are not role- or reputation-based; `_derive_weight()` returns `1.0` unless an explicit weight is supplied.

## Tests And Source References

Primary implementation and verification files:

- `schemas/postgres/161_delphi.sql` — core seven-table schema and three views
- `schemas/postgres/170_delphi_threat_resolution.sql` — diversity, consent,
  minority, stopping, forecast, and calibration additions
- `services/delphi/models.py` — Pydantic data models and defaults
- `services/delphi/consensus.py` — aggregate statistics and stopping helpers
- `services/delphi/panel.py` — panel membership, tokens, weights, diversity
- `services/delphi/facilitator.py` — study, contribution, consensus, and
  recommendation operations
- `services/delphi/minority.py` — minority-report workflow
- `services/agents/delphi_facilitator_agent.py` — summary and draft agent
- `services/export/report_generator.py` — public Delphi dissent context
- `tests/test_delphi.py` — model, consensus, facilitator, panel, agent, and CLI
  tests
- `tests/test_prediction_calibration.py` — migration checks for calibration and
  related Delphi schema additions

Current tests do not fully cover approval diversity/minority gates, consent,
public-view SQL behavior, minority reports, forecast calibration persistence,
stopping-evaluation persistence, or the actual `list-studies` result shape.

## Operational Workflow

### Before Opening

1. State the decision question, scope, sponsor, intended use, and non-binding or binding status.
2. Select an item scale and set IQR/stability thresholds relative to that scale.
3. Define recruitment, representation, conflicts, consent, privacy, retention, and withdrawal procedures.
4. Review expert-weight policy and document why weighting is legitimate for this study.
5. Avoid identity-revealing custom display tokens and redact unnecessary personal data from reasoning.
6. Test all items for clarity, neutrality, and accessibility.

### While Open

1. Monitor participant count by stakeholder group outside aggregate consensus alone.
2. Review median, IQR, weighted median, and disagreement together.
3. Treat `consensus_reached` as a configured statistical condition, not substantive truth.
4. Review extreme reasoning for safety and privacy before redistributing summaries.
5. Record facilitation interventions and avoid steering participants toward the current median.
6. Run `check-stopping`, but document the human rationale for continuing or closing.

### Closing and Publication

1. Check completion, duration, stability, dissent, and representation.
2. Generate an agent or human summary and verify every claim against stored aggregates.
3. Draft a recommendation that separates consensus, disagreement, uncertainty, and minority views.
4. Obtain approval from an authenticated, authorized human.
5. Close the study explicitly.
6. Publish only through the approved aggregate view or another reviewed release path.
7. Preserve an audit record of criteria, weights, exclusions, approval, and any downstream decision.
