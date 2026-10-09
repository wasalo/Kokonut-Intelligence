# Screenshots

Add platform screenshots here for documentation. Recommended sizes:

- **Dashboard overview**: 1200x800 (16:9)
- **Mobile view**: 375x812 (iPhone)
- **Data entry form**: 1200x800
- **Metabase dashboard**: 1200x800

## Naming Convention

- `dashboard-overview.png`
- `data-entry-form.png`
- `metabase-eagle-view.png`
- `metabase-farm-operations.png`
- `attestation-flow.png`
- `mobile-field-worker.png`

## How to Capture

1. Start core services: `docker compose up -d`. To capture Metabase, start it separately with `docker compose --profile metabase up -d metabase`.
2. Access Directus at https://localhost/admin, or http://localhost:8055 if a local override exposes Directus directly
3. Access optional Metabase at http://localhost:3001 when its profile is enabled
4. Take screenshots of key workflows
5. Save to this directory
