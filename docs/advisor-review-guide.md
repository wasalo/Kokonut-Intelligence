# Advisor Review Guide

Advisors review EBF scorecards for rubric fitness, evidence quality,
calibration consistency, and claim safety. This guide covers the advisor's
role in the Evidence-Based Framework, the scoring engine, calibration
workflow, publication gates, and agent boundaries.

For scorecard lifecycle and evidence gate details, see `ebf-scorecard.md`.
For trust graph provenance, see `ebf-trust-graph.md`.

## The seven EBF pillars

EBF scorecards evaluate syntropic farms across seven ecological benefit
pillars. Each pillar maps to an `impact_framework` dimension and has a
default metric.

| Sort | Pillar key | Pillar name | Framework | Default metric |
|---|---|---|---|---|
| 1 | `air_quality` | Air Quality | `ebf_environmental` | `kg_co2e_per_acre` |
| 2 | `water_management` | Water Management | `ebf_environmental` | `runoff_reduction_pct` |
| 3 | `soil_health` | Soil Health | `ebf_environmental` | `soc_change_pct` |
| 4 | `biodiversity` | Biodiversity | `ebf_environmental` | `species_richness_index` |
| 5 | `carbon_sequestration` | Carbon Sequestration | `ebf_sustainability` | `total_farm_co2e` |
| 6 | `equity_community` | Equity & Community | `ebf_social` | `local_worker_pct` |
| 7 | `implementation_quality` | Implementation Quality | `ebf_sustainability` | `smart_kpi_completion` |

Seeded in `schemas/seeds/032_ebf_rubric.sql` with 70 rubric bands (7 pillars ×
10 scores) under rubric version `2026.1`.

## Review scope

Advisors should confirm:

1. **Rubric fitness** — the seven EBF pillars are scored with the active
   rubric version (`2026.1`). Verify `ebf_scorecard.rubric_version` matches
   the seeded rubric bands.
2. **Farm-specific metric profiles** — when defaults do not fit local context,
   `ebf_farm_metric_profile` rows justify the alternative metric with a
   `rationale` and `data_source`.
3. **Evidence links** — each `ebf_score` has at least one `ebf_score_evidence`
   link with an appropriate `evidence_type` and `evidence_maturity_level`.
4. **Public maturity** — public scorecards meet Level 4 evidence maturity or
   higher. Public carbon pillar scores meet Level 6.
5. **Claim safety** — carbon pillar scores link to a published third-party
   verified `impact_claim` with `claim_category='carbon'`,
   `claim_type='third_party_verified_claim'`, `evidence_maturity=6`, and
   non-empty `external_verifier` and `methodology_ref`.
6. **Stakeholder feedback** — feedback is aggregated or public-consented
   before use in public equity narratives. Raw private text is never exposed.
7. **Calibration consistency** — calibration sessions use the correct method,
   frequency, and have a report URL or hash when required.

## Evidence maturity gates

Two levels of evidence maturity are enforced at both the database constraint
and Python gate levels:

### General scores (non-carbon)

- `evidence_maturity_level >= 4` (Reviewed record or higher)
- At least one `ebf_score_evidence` link required
- Enforced by `chk_ebf_score_public_maturity` DB constraint and
  `public_score_allowed()` in `services/scoring/gates.py`

### Carbon sequestration scores

- `evidence_maturity_level = 6` (Third-party verified)
- At least one `ebf_score_evidence` link required
- Must link to a published `impact_claim` with:
  - `claim_category = 'carbon'`
  - `claim_type = 'third_party_verified_claim'`
  - `evidence_maturity = 6`
  - `external_verifier` non-empty
  - `methodology_ref` non-empty
- Enforced by `chk_ebf_score_public_carbon_level6` DB constraint and
  `public_carbon_score_allowed()` + `linked_carbon_claim_allowed()` in gates.py

### Scorecard-level gate

- `evidence_maturity_level >= 4`
- `public_claim_allowed = TRUE`
- All 7 pillars must have public-safe scores
- All 7 pillars must have evidence links
- Carbon pillar must meet Level 6
- Location must have a verified/published `farm_registry_record`
- Enforced by `chk_ebf_scorecard_public_maturity` DB constraint and
  `scorecard_publication_gate()` in gates.py

## Scoring engine

### Pillar calculators

Seven calculators in `services/scoring/calculators.py` normalize governed
metric values to 0–10 scores:

| Calculator | Input metric | Input range | Formula |
|---|---|---|---|
| `compute_air_quality_score` | `kg_co2e_per_acre` | 0–5000 | linear(0, 5000) |
| `compute_water_management_score` | `runoff_reduction_pct` | 0–100% | percentage |
| `compute_soil_health_score` | `soc_change_pct` | -2 to 8 | linear(-2, 8) |
| `compute_biodiversity_score` | `species_richness_index` | 0–100 | linear(0, 100) |
| `compute_carbon_sequestration_score` | `total_farm_co2e / farm_area_ha` | 0–20 tCO2e/ha | linear(0, 20) |
| `compute_equity_community_score` | `local_worker_pct` + `training_hours` | composite | avg(percentage, linear(0,40)) |
| `compute_implementation_quality_score` | `smart_kpi_completion_pct` | 0–100% | percentage |

### Normalization functions

In `services/scoring/normalization.py`:

| Function | Formula |
|---|---|
| `clamp_score(value)` | Clamp to 0–10 |
| `normalize_linear(value, min, max)` | `(value - min) / (max - min) × 10`, clamped |
| `normalize_percentage(value)` | `value / 100 × 10`, clamped |

### Rubric bands

In `services/scoring/rubric.py`, 10 integer bands per pillar (70 total)
with five labels:

| Score range | Label |
|---|---|
| 0–1 | insufficient |
| 2–3 | emerging |
| 4–5 | developing |
| 6–7 | strong |
| 8–10 | leading |

Each band in `ebf_rubric_band` includes `description`, `required_practices`,
and `evidence_requirements` arrays.

### Confidence labels

In `services/scoring/confidence.py`:

**Score-level confidence** (based on evidence count, maturity, and public-safe
evidence count):

| Label | Conditions |
|---|---|
| `high` | maturity ≥ 5, evidence ≥ 3, public-safe ≥ 2 |
| `moderate` | maturity ≥ 4, evidence ≥ 2, public-safe ≥ 1 |
| `low` | evidence ≥ 1, maturity ≥ 2 (but not high/moderate) |
| `insufficient_evidence` | no evidence or maturity ≤ 1 |

**Scorecard-level confidence** (conservative roll-up):

| Label | Conditions |
|---|---|
| `high` | all pillars high |
| `moderate` | all pillars high or moderate |
| `low` | at least one pillar low (none insufficient) |
| `insufficient_evidence` | any pillar insufficient |

## Calibration workflow

### Calibration sessions

`ebf_calibration_session` tracks calibration events with:

| Field | Constraints | Notes |
|---|---|---|
| `calibration_frequency` | CHECK: `annual`, `semi_annual`, `quarterly`, `custom` | Pilot: semi-annual; Network: annual |
| `calibration_method` | CHECK: `third_party`, `team_with_report`, `mixed_panel` | Third-party preferred |
| `report_url` | TEXT | Required for team calibration before verify/publish |
| `report_hash` | VARCHAR(64) | Alternative to report_url |
| `participants` | JSONB array | Panel member identities |
| `status` | lifecycle: draft → submitted → verified → published → rejected | |

**Report requirement constraint:** Team calibration (`team_with_report` or
`mixed_panel`) requires `report_url` or `report_hash` before the session
can be verified or published. Third-party calibration is exempt.

### Calibration decisions

`ebf_calibration_decision` records individual score adjustments:

| Field | Type | Notes |
|---|---|---|
| `session_id` | UUID FK → `ebf_calibration_session` | |
| `scorecard_id` | UUID FK → `ebf_scorecard` | |
| `score_id` | UUID FK → `ebf_score` | |
| `pillar_id` | UUID FK → `ebf_pillar` | |
| `previous_score` | NUMERIC(3,1), 0–10 | score before adjustment |
| `adjusted_score` | NUMERIC(3,1), 0–10 | score after adjustment |
| `reason` | TEXT NOT NULL | justification for change |
| `evidence_reference` | TEXT | supporting evidence |
| `decision_status` | CHECK: draft, submitted, verified, rejected | |

### Recommended cadence

- **Semi-annual** for pilot farms
- **Annual** for network farms
- **Additional** after major methodology, land-use, or evidence-source changes

### Calibration history view

`v_ebf_calibration_history` aggregates sessions with decision counts:

```sql
SELECT session_name, location_name, session_date, rubric_version,
       calibration_frequency, calibration_method, status,
       decision_count, verified_decision_count, report_url
FROM v_ebf_calibration_history
ORDER BY session_date DESC;
```

## Evidence gap analysis

The `v_ebf_evidence_gap_summary` view classifies each pillar score into one
of five gap statuses:

| Gap status | Meaning |
|---|---|
| `missing_evidence` | No `ebf_score_evidence` links |
| `below_public_threshold` | `evidence_maturity_level < 4` |
| `carbon_requires_level6` | Carbon pillar with maturity < 6 |
| `low_confidence` | Confidence is `low` or `insufficient_evidence` |
| `ready_for_review` | All gates satisfied |

### Evidence gap agent

```bash
python3 -m services.agents.ebf_evidence_gap_agent --scorecard-id UUID
```

Read-only analysis that queries `v_ebf_evidence_gap_summary` and generates
recommendations for pillars with `gap_status != 'ready_for_review'`.

## Publication gates

### Score-level gate

`score_publication_gate(pillar_key, evidence_maturity_level, has_evidence_link, linked_impact_claim)` in
`services/scoring/gates.py`:

- **Non-carbon:** `evidence_maturity_level >= 4` AND evidence link present
- **Carbon:** `evidence_maturity_level = 6` AND evidence link AND published
  third-party verified carbon impact claim

### Scorecard-level gate

`scorecard_publication_gate(evidence_maturity_level, pillar_results)`:

- `evidence_maturity_level >= 4`
- All 7 pillar scores must pass their individual gates
- Returns `(allowed: bool, reasons: list[str])`

### DB constraints

| Constraint | Enforces |
|---|---|
| `chk_ebf_scorecard_public_maturity` | published → maturity ≥ 4 AND public_claim_allowed |
| `chk_ebf_scorecard_calibration_report` | verified/published → report_url or report_hash (unless third-party) |
| `chk_ebf_score_public_maturity` | public_score_allowed → maturity ≥ 4 |
| `chk_ebf_score_public_carbon_level6` | public carbon → maturity = 6 |

## Agent boundaries

Three EBF agents support advisors. All are draft-only; agents cannot verify,
publish, or raise evidence maturity.

### EBF scorecard draft agent

```bash
python3 -m services.agents.ebf_scorecard_agent --location-id UUID --period-start DATE --period-end DATE
```

Creates a draft scorecard workspace with `rubric_version: "2026.1"`. Does not
write to the database. Output: `{scorecard, evidence_gaps, safety_note}`.

**Safety:** `assert_agent_action_allowed("create", "ebf_scorecard", {"status": "draft", "evidence_maturity_level": 1})`

### EBF calibration memo agent

```bash
python3 -m services.agents.ebf_calibration_agent --session-id UUID
```

Drafts a calibration memo structure with `proposed_decisions`. Does not write
to the database. Output: `{memo, proposed_decisions, safety_note}`.

**Safety:** `assert_agent_action_allowed("create", "ebf_calibration_decision", {"decision_status": "draft"})`

### EBF evidence gap agent

```bash
python3 -m services.agents.ebf_evidence_gap_agent --scorecard-id UUID
```

Read-only analysis of evidence gaps. Queries `v_ebf_evidence_gap_summary`.
Output: `{evidence_gaps: [...], recommendations: [...]}`.

**Safety:** `assert_agent_action_allowed("read", "ebf_scorecard", ...)`

### Agent restrictions

| Action | Allowed? |
|---|---|
| Draft scorecard | yes |
| Draft calibration memo | yes |
| Analyze evidence gaps | yes (read-only) |
| Verify scorecard | no |
| Publish scorecard | no |
| Raise evidence maturity above 3 | no |
| Certify carbon claims | no |
| Expose private stakeholder feedback | no |

Agent outputs are draft aids for human review, not publication authority.
Enforced by `GOVERNED_COLLECTIONS` in `services/agents/safety.py` and
`AGENT_ALLOWED_EBF_STATUSES = {"draft", "submitted", "rejected"}`.

## Trust graph

The EBF trust graph records provenance relationships around scorecards,
pillar scores, evidence, reviewers, calibration sessions, attestations,
reports, dashboards, and recommendations. 17 node types and 11 edge types
are supported.

See `ebf-trust-graph.md` for full details on node/edge types, public safety
filtering, Mermaid rendering, and dashboard use.

## CLI commands

### Scoring CLI

```bash
python3 -m services.scoring --scorecard-id UUID --export public
python3 -m services.scoring --scorecard-id UUID --export internal
python3 -m services.scoring --trust-graph UUID
python3 -m services.scoring --trust-graph UUID --public-safe
python3 -m services.scoring --trust-graph UUID --mermaid
```

### Agent CLIs

```bash
python3 -m services.agents.ebf_scorecard_agent --location-id UUID --period-start DATE --period-end DATE
python3 -m services.agents.ebf_calibration_agent --session-id UUID
python3 -m services.agents.ebf_evidence_gap_agent --scorecard-id UUID
```

### Report generator

```bash
python3 -m services.export.report_generator --type ebf_scorecard --location-id UUID
```

## Database tables

11 EBF tables across 2 schema files:

| Schema | Tables |
|---|---|
| `032_ebf_scorecard.sql` | `ebf_pillar`, `ebf_rubric_band`, `ebf_scorecard`, `ebf_score`, `ebf_score_evidence` |
| `033_ebf_p1_operations.sql` | `ebf_farm_metric_profile`, `ebf_calibration_session`, `ebf_calibration_decision`, `ebf_trust_graph_node`, `ebf_trust_graph_edge`, `ebf_improvement_recommendation` |

### Public views (5)

| View | Purpose |
|---|---|
| `v_public_ebf_scorecard` | Per-pillar public view with all evidence gates |
| `v_public_ebf_scorecard_summary` | Scorecard summary requiring all 7 pillars |
| `v_public_ebf_pillar_summary` | Cross-farm pillar aggregation with caveats |
| `v_ebf_evidence_gap_summary` | Evidence gap matrix with 5 gap statuses |
| `v_ebf_calibration_history` | Calibration session history with decision counts |

### Governed metrics (8)

`ebf_air_quality_score`, `ebf_water_management_score`,
`ebf_soil_health_score`, `ebf_biodiversity_score`,
`ebf_carbon_sequestration_score`, `ebf_equity_community_score`,
`ebf_implementation_quality_score`, `ebf_overall_score`

## Testing

```bash
python3 -m tests.test_ebf_p0
python3 -m tests.test_ebf_p1
python3 -m tests.test_ebf_p2
python3 -m tests.test_ebf_agents
python3 -m tests.test_ebf_agent_safety
python3 -m tests.test_ebf_calibration
python3 -m tests.test_ebf_scoring
python3 -m tests.test_ebf_gates
python3 -m tests.test_ebf_carbon_gates
python3 -m tests.test_ebf_public_views
python3 -m tests.test_ebf_trust_graph
python3 -m tests.test_ebf_schema
python3 -m tests.test_ebf_privacy
python3 -m tests.test_ebf_equity_scoring
python3 -m tests.test_ebf_csv_import
python3 -m tests.test_ebf_cids
python3 -m tests.test_ebf_json_export
python3 -m tests.test_ebf_dashboard
python3 -m tests.test_ebf_pilot_seed
```

| Test file | Coverage |
|---|---|
| `test_ebf_p0.py` | Schema tables, views, lifecycle, gates, seed pillars, 70 rubric bands, 8 metric definitions |
| `test_ebf_p1.py` | Operational tables, lifecycle, trust graph, gap views, dashboards, confidence, export, CSV templates |
| `test_ebf_p2.py` | Dashboard rollup, CIDS mapping, scorecard guide, trust graph guide, advisor guide |
| `test_ebf_agents.py` | Agent output format (draft only, memo structure, gap summary) |
| `test_ebf_agent_safety.py` | Agents cannot publish or raise EBF maturity; task writes are draft-only |
| `test_ebf_calibration.py` | Calibration lifecycle constraints, team calibration requires report |
| `test_ebf_scoring.py` | All 7 pillar calculators return 0–10; carbon requires positive area |
| `test_ebf_gates.py` | Publication gates match maturity rules; Level 4/Level 6 enforcement |
| `test_ebf_carbon_gates.py` | Carbon requires Level 6; linked carbon claim requires verifier and methodology |
| `test_ebf_public_views.py` | Public views filter to published + registry-backed; require 7 pillars |
| `test_ebf_trust_graph.py` | Mermaid rendering of trust graph |
| `test_ebf_schema.py` | All 11 EBF tables declared; ebf_score links to impact_claim |
| `test_ebf_privacy.py` | Equity feedback synthesis omits raw private text |
| `test_ebf_equity_scoring.py` | Equity score uses aggregate feedback only; safety note present |
| `test_ebf_csv_import.py` | CSV validation, dry-run import |
| `test_ebf_cids.py` | EBF scores export as `cids:IndicatorReport` |
| `test_ebf_json_export.py` | JSON export format validation |
| `test_ebf_dashboard.py` | Dashboard dataset seeds and SQL files exist |
| `test_ebf_pilot_seed.py` | Adelphi pilot is idempotent draft shell, does not fabricate scores |
