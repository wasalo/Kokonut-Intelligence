# Strategy Markup Export

PostgreSQL/Directus remains the canonical strategy store. The
`services.strategy_markup` package provides a read-only StratML Part 1 XML
projection for machine-readable exchange. Exporting does not publish, persist,
or mutate governed strategy records.

## Export

The package entrypoint exports one strategy plan:

```bash
python3 -m services.strategy_markup \
  --plan-id UUID \
  --output exports/strategy.xml \
  --source-url https://example.org/strategy
```

Arguments:

- `--plan-id` is required and identifies one `strategy_plan` row.
- `--output` is optional. Without it, XML is printed to stdout; with it, the
  exporter writes UTF-8 XML with an XML declaration to that exact path.
- `--source-url` is optional and is copied into the StratML `Source` element.
  It is caller-supplied metadata; the exporter does not validate, canonicalize,
  fetch, or verify the URL.
- `--allow-draft` permits internal export of plans that would otherwise fail
  eligibility checks.

Parent directories for `--output` are not created automatically.

## Eligibility

Without `--allow-draft`, the plan must have status `approved` or `active`.
The exporter also requires a non-empty plan ID and name and a planning horizon
whose end is not before its start. Missing plans raise `StratMLExportError`.
Other database, filesystem, or malformed-input errors may propagate as their
underlying exceptions.

`--allow-draft` is an internal-review override, not a publication or approval
operation. It does not change the plan status.

## Source Selection

The exporter reads:

- One `strategy_plan` row.
- All `strategy_map` rows for that plan, ordered by strategic theme, perspective,
  statement, and ID.
- Approved `vision_mission` rows whose `entity_type` matches the plan scope and
  whose `entity_id` matches the plan scope ID or is global (`NULL`).

The exporter currently does not filter strategy-map entries by their
`visibility` (`private`, `limited`, or `public`) or by strategy-map status.
Exports may therefore contain private or limited entries and should be treated
as internal unless the caller has applied an appropriate export policy.

Multiple approved statement versions are fetched. The document builder keeps
one vision and one mission by statement type, while values are all emitted in
sorted order. Consumers should not assume that version selection is a complete
latest-version policy.

## XML Mapping

The output uses the ISO StratML core namespace and contains `StrategicPlan`,
`Name`, `StrategicPlanCore`, and `AdministrativeInformation` elements.

The current mapping is:

- `diagnosis_summary` becomes `Description`, falling back to `guiding_policy`.
- `guiding_policy`, `theory_of_change`, and `uncertainty_summary` are combined
  into one newline-separated `OtherInformation` element.
- Approved vision and mission statements become `Vision` and `Mission`, each
  with a description and stable XML identifier.
- Approved values become `Value` elements with names and stable identifiers.
- Strategy-map entries become StratML `Objective` elements grouped into
  `Goal` elements by `strategic_theme`, then `perspective`, then `General`.
- Objective descriptions may include perspective, target value and unit,
  current value, and status.
- Strategy-map status values are `on_track`, `at_risk`, `behind`, `achieved`,
  and `not_started`.
- Stable identifiers are generated for plans, goals, objectives, visions,
  missions, and values; they are not copied verbatim as XML IDs.
- Goal and objective sequence indicators are generated from deterministic
  alphabetical export ordering. They are not persisted planning sequence data.
- Planning horizon dates become `StartDate` and `EndDate`.
- `PublicationDate` uses an explicit builder `export_date` when provided,
  otherwise the plan's `approved_at`, otherwise the current UTC date. The CLI
  does not expose an export-date option.

## Validation

`services.strategy_markup.validator.validate_strategy` validates normalized
strategy documents for name, horizon, approved/active status, duplicate IDs,
indicator references, reporting periods, and value-chain references. The
database-backed CLI exporter does not currently load performance indicators or
value-chain links into its XML output.

`validate_xml_document` is a minimal structural check. It verifies that XML is
parseable, the root ends in `StrategicPlan`, `Name` exists,
`StrategicPlanCore` exists, and every `Objective` has an `Identifier`. It is not
complete StratML schema validation and does not validate all dates, URLs,
administrative fields, namespaces, or Part 2 structures.

## Current Boundaries

The exporter currently emits only the Part 1-style plan core described above.
It does not emit `strategy_performance_indicator`,
`strategy_value_chain_link`, or `strategy_relationship` records, and it does
not provide performance reporting, forecasting, XML import, document hashing,
JSON-LD/RDF export, or cross-organization discovery.

Migration `schemas/postgres/307_strategy_markup_projection.sql` provides schema
groundwork for performance indicators, value-chain links, relationships, and an
imported-document registry. Those tables are not currently consumed by the
exporter, and exports are not registered there.

The output is deterministic for the same plan, rows, statements, and explicit
export date. Without an explicit date, plans lacking `approved_at` receive the
current UTC publication date and may produce different output on later runs.

## Tests And References

- Exporter: `services/strategy_markup/exporter.py`
- Package entrypoint: `services/strategy_markup/__main__.py`
- IDs and normalization: `services/strategy_markup/ids.py`, `services/strategy_markup/mapping.py`
- Validation: `services/strategy_markup/validator.py`
- Strategy-map schema: `schemas/postgres/208_strategy_map.sql`
- Vision/mission schema: `schemas/postgres/209_vision_mission.sql`
- Strategy-plan schema: `schemas/postgres/256_strategy_plans.sql`
- Projection groundwork: `schemas/postgres/307_strategy_markup_projection.sql`
- Focused tests: `tests/test_strategy_markup.py`

The focused tests cover deterministic ordering, draft handling, horizon
validation, stable identifiers, normalized-document validation, and minimal XML
validation. They do not currently cover database row selection, visibility
filtering, statement-version selection, CLI file output, source URL handling,
or end-to-end database export behavior.
