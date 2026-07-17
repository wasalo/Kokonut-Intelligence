# Strategy Markup Export

Kokonut Intelligence keeps PostgreSQL/Directus as the canonical strategy
store. The StratML exporter provides a deterministic, read-only projection for
machine-readable exchange and publication.

## Export

Export an approved or active strategy plan as StratML Part 1 XML:

```bash
python3 -m services.strategy_markup \
  --plan-id UUID \
  --output exports/strategy.xml \
  --source-url https://example.org/strategy
```

Draft plans are rejected by default. For internal review only:

```bash
python3 -m services.strategy_markup --plan-id UUID --allow-draft
```

The projection includes:

- Strategy plan name, diagnosis, guiding policy, theory of change, and uncertainty.
- Approved vision, mission, and values statements scoped to the plan.
- Strategy-map entries grouped into StratML goals by strategic theme or perspective.
- Objective identifiers, sequence order, perspective, target/current values, unit, and status.
- Planning horizon, publication date, and optional authoritative source URL.

The exporter does not publish or mutate governed records. It is intended as the
first interchange layer for future StratML Part 2 performance reporting,
JSON-LD/RDF projections, and cross-organization strategy discovery.
