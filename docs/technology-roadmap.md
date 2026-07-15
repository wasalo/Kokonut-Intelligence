# Technology Roadmap

The technology roadmap is a governed planning layer connecting enterprise
needs to capabilities, technology areas, measurable drivers, alternatives, and
human review. It complements the strategy map, capability map, value streams,
and portfolio rather than replacing them.

## Data Model

- `technology_roadmap`: planning horizon, owner, sponsor, detail level, and lifecycle.
- `technology_roadmap_requirement`: business, customer, operational, regulatory, or sustainability need.
- `technology_area`: major technology domain within a roadmap.
- `technology_driver`: measurable selection criterion linked to a requirement.
- `technology_alternative`: option, maturity, confidence, cost, recommendation, and rationale.
- `technology_roadmap_review`: human review history and evidence.

The portfolio view is `v_technology_roadmap_overview`. Roadmap records use the
governed lifecycle and do not imply that an alternative is approved for
deployment. A human review is required before a roadmap is approved or
superseded.

## CLI

```bash
python3 -m services.analytics.cli_technology_roadmap list
python3 -m services.analytics.cli_technology_roadmap show ROADMAP_UUID
python3 -m services.analytics.cli_technology_roadmap recommend ROADMAP_UUID
python3 -m services.analytics.cli_technology_roadmap review ROADMAP_UUID approved --reviewed-by REVIEWER_UUID
```

The executive report is generated with:

```bash
python3 -m services.export.report_generator --type technology_roadmap --location-id LOCATION_UUID
```

Roadmap recommendations are advisory. They should be linked to strategy,
capability, value-stream, initiative, and evidence records before execution
work is authorized.
