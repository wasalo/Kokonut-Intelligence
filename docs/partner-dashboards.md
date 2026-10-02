# Partner Dashboard Guide

Kokonut Intelligence supports Directus dashboards, optional Metabase dashboards, and custom partner applications. These are presentation and integration layers over the canonical PostgreSQL/Directus records. They do not replace lifecycle review, evidence gates, consent controls, or server-side authorization. Metabase is excluded from default Compose deployments; the repository dashboard assets remain available for product discovery.

## Deployment Topology

- PostgreSQL and ClickHouse remain private to the Compose networks.
- Directus is the canonical schema/API layer.
- When explicitly enabled, Metabase is an optional BI layer and stores its own application metadata in the separate `metabase` database.
- Partner analytics connect Metabase to the `kokonut_intelligence` PostgreSQL database.
- Base Compose exposes Caddy, not Directus or Metabase database ports.
- Default Caddy routes Directus through `/directus/*` and `/admin/*`; Metabase is not routed through default Caddy.
- A separately launched gateway on port `8099` is an API integration surface, not the default dashboard proxy.

Default Compose and optional Metabase URLs are:

| Service | URL |
|---|---|
| Directus API | `https://localhost/directus` |
| Directus admin | `https://localhost/admin` |
| Metabase (opt-in) | `http://localhost:3001` after enabling `--profile metabase` |

Use the effective Compose or reverse-proxy configuration for the deployment. Enable local Metabase with `docker compose --profile metabase up -d metabase`; `http://localhost:3001` is available through the local override. Production routing is a separate opt-in through the Traefik overlay.

## Approaches At A Glance

| Approach | Flexibility | Complexity | Maintenance | Best for |
|---|---:|---:|---:|---|
| Directus dashboard | Medium | Low | Low | Internal operations and governed collection views |
| Metabase dashboard | High | Medium | Medium | BI analysis, parameterized reports, and partner reporting |
| Custom React app | Full | High | High | White-label experiences and specialized workflows |
| Gateway/API integration | API-focused | Medium | Medium | Backend integrations and controlled public reads |

## Directus Dashboards

Directus dashboards are appropriate for authenticated internal users who already have Directus permissions. Configure them in the Directus admin UI and use the existing role, policy, field, and row filters rather than creating a client-side security boundary.

### Setup

1. Start Compose with encrypted secrets loaded:

```bash
source scripts/load-secrets.sh
docker compose up -d
```

2. Open the Directus admin URL for the deployment.
3. Create a dashboard and add panels for approved collections or views.
4. Apply the least-privilege role and location filters through Directus permissions.
5. Validate the dashboard with a test account from each partner role.

Dashboard panels should use governed or public-safe sources. Do not expose raw private stakeholder feedback, unverified metrics, private evidence, or unrestricted operational tables to a partner role.

### Sharing And Embedding

Directus sharing and embedding are deployment-sensitive. The base Caddy configuration sends `X-Frame-Options: DENY`, so an iframe will not be a supported cross-origin integration until the reverse proxy, origin policy, and frame headers are deliberately configured and reviewed. Do not work around this by exposing Directus directly or disabling security headers globally.

If embedding is approved, use the deployment’s `/directus` or `/admin` path and test:

- authenticated session behavior;
- allowed parent origins;
- cookie and SameSite behavior;
- role and location filters;
- logout and session expiry;
- frame and content-security headers.

## Metabase Dashboards

Metabase dashboard assets live under `dashboards/metabase/`:

- `*.json` files are import templates;
- `sql/*.sql` files are the backing native queries;
- `dashboards/metabase/README.md` lists the available dashboard assets and import workflow.

The repository does not automatically import every JSON dashboard into Metabase. After Metabase is initialized, import the required templates or recreate the questions through the Metabase UI/API, then review their permissions and filters.

### Setup

1. Load secrets and start Compose:

```bash
source scripts/load-secrets.sh
docker compose up -d
```

2. Create or access the Metabase administrator account.
3. If using `scripts/seed-metabase.sh`, apply a local/debug Compose override that maps Metabase to `localhost:3000`; the base Compose configuration keeps Metabase private and the script probes that host port.
4. Add the `kokonut_intelligence` PostgreSQL database as the analytics database:

| Setting | Value |
|---|---|
| Host | `database` |
| Port | `5432` |
| Database | `kokonut_intelligence` |
| User | `kokonut` |
| Password | Runtime `POSTGRES_PASSWORD` |

Metabase’s application metadata database is configured separately in Compose as `metabase`; it is not the partner analytics source.

5. Import the required JSON templates or create questions from the matching SQL files.
6. Apply Metabase collection, group, database, and embedding permissions.
7. Validate each dashboard with a restricted partner account before sharing it.

### Dashboard Families

The repository includes operational, financial, environmental, attestation, evidence, stakeholder, governance, EBF, scaling, commons, wellbeing, ecological, and other domain dashboards. Important governance-oriented assets include:

| Dashboard family | Source |
|---|---|
| Location overview | `dashboards/metabase/00_location_overview.json` and SQL |
| Farm operations | `dashboards/metabase/01_farm_operations.json` and SQL |
| Crop NOI | `dashboards/metabase/02_crop_noi.json` and SQL |
| Evidence gaps | `dashboards/metabase/20_evidence_gap_dashboard.json` and SQL |
| Stakeholder feedback | `dashboards/metabase/21_stakeholder_feedback_dashboard.json` and SQL |
| EBF scorecard | `dashboards/metabase/22_ebf_scorecard.json` and SQL |
| EBF evidence/calibration | `dashboards/metabase/sql/23_ebf_evidence_gap.sql`, `23_evidence_gap_ebf.sql`, and `24_ebf_calibration_history.sql` |
| EBF portfolio views | `dashboards/metabase/24_portfolio_ebf.json` and `25_ebf_portfolio_messy_rollup.sql` |
| Participatory governance | `dashboards/metabase/27_participatory_governance.json` and SQL |

Public EBF portfolio outputs are confidence-labelled roll-ups and must not be presented as rankings of interchangeable farms. Internal evidence-gap and calibration dashboards are not public-safe by default.

### Signed Embedding

Metabase embedding uses the configured `METABASE_EMBEDDING_SECRET_KEY`, which Compose passes to Metabase as `MB_EMBEDDING_SECRET_KEY`. Keep the secret in encrypted runtime configuration and generate short-lived tokens in a trusted backend, never in browser code.

Conceptual token generation is:

```python
import os
import time
import jwt


def get_metabase_embed_url(dashboard_id: int, params: dict | None = None) -> str:
    token = jwt.encode(
        {
            "resource": {"dashboard": dashboard_id},
            "params": params or {},
            "exp": int(time.time()) + 300,
        },
        os.environ["METABASE_EMBEDDING_SECRET_KEY"],
        algorithm="HS256",
    )
    return f"{os.environ['METABASE_URL']}/embed/dashboard/{token}"
```

The backend must derive permitted locations and filters from authenticated partner identity. Never accept an arbitrary location list from the browser as the authorization decision.

Before enabling iframe embedding, review the current Caddy `X-Frame-Options: DENY` header and configure an explicit, narrowly scoped frame policy for the approved parent origins. Signed tokens do not replace Metabase permissions or reverse-proxy security review.

## Governed Dashboard Datasets

`dashboard_dataset` is the platform registry for refreshable BI/frontend datasets. Each row contains:

- name and description;
- `dataset_type`;
- optional `location_id`;
- stored `query_sql`;
- refresh interval and `last_refreshed_at`;
- governed lifecycle `status`;
- metadata such as owner, refresh cron, public-safety caveats, and last-refresh details.

The lifecycle is the standard governed lifecycle:

```text
draft -> submitted -> verified -> published
draft -> rejected -> draft
```

Dashboard dataset verification requires an analyst, manager, or admin role. Publication requires a manager or admin role. Agents may only create or update safe draft/submitted/rejected states and cannot verify or publish datasets.

### Refresh Operations

```bash
python3 -m services.export.dataset_refresh --list
python3 -m services.export.dataset_refresh --dataset-id UUID
python3 -m services.export.dataset_refresh --all
```

The scheduled database task `dashboard_dataset_refresh` runs `--all` every six hours with bounded timeout and retries. Refresh executes the stored SQL, records row count/duration/status in `metadata.last_refresh`, and updates `last_refreshed_at`. A failed query records an error result rather than making the dataset valid.

Current implementation note: the `--list` and `--all` paths filter for `status = 'active'`, while seeded datasets use the lifecycle values `published` and `verified`. Until that implementation mismatch is corrected, use `--dataset-id UUID` for a specific dataset and do not claim that `--all` refreshes every published dataset.

## Data Safety And Publication

- `PUBLIC_RESTRICT=true` disables unauthenticated Directus data access.
- Public dashboards must use public-safe views or datasets, not raw private tables.
- Public metric summaries expose verified metrics only.
- Public stakeholder feedback requires explicit consent, a public-safe consent scope, published status, `is_public = TRUE`, and a non-empty `public_summary`.
- Public impact claims require the applicable evidence maturity gate; public carbon claims require Level 6, an external verifier, methodology reference, and published status.
- Reports and dashboards must preserve uncertainty, limitations, negative findings, and affected-community voice where available.
- Never include raw private feedback, private evidence, database passwords, API keys, Directus admin tokens, or Metabase embedding secrets in browser bundles, SQL exports, screenshots, or URLs.
- Dashboard filters improve usability but do not replace Directus, Metabase, gateway, or database authorization.

## Custom React Partner Application

Use a custom application when a partner needs a white-label workflow or visualizations not supported by Directus/Metabase. Keep authorization server-side and use the Directus SDK or gateway only with scoped credentials.

```typescript
import { createDirectus, readItems, rest } from "@directus/sdk";

const directus = createDirectus(
  process.env.DIRECTUS_URL ?? "https://localhost/directus",
).with(rest());

const farms = await directus.request(
  readItems("farm", {
    fields: ["id", "name", "total_area", "location_id"],
  }),
);
```

For browser applications, prefer an authenticated user session or a backend-for-frontend. Do not ship `DIRECTUS_ADMIN_TOKEN`, `KOKONUT_API_KEYS`, `GRPC_API_KEY`, or `METABASE_EMBEDDING_SECRET_KEY` to the client.

Use server-side Directus permission filters and public-safe views. A client-supplied `partnerLocationIds` array is not a security boundary.

## Gateway/API Integration

The optional gateway exposes explicit public-read routes such as:

- `GET /api/locations`
- `GET /api/locations/{location_id}`
- `GET /api/metrics/{location_id}`
- `GET /api/crisp/{location_id}`
- `GET /api/analytics/{location_id}/summary`

Unknown routes remain protected. API keys use `KOKONUT_API_KEY_SCOPES` and fail closed without a matching scope. Capability tokens support resource/action, expiration, revocation, usage, and optional location constraints.

Do not describe the gateway as strict end-to-end location authorization for every route: current propagation is incomplete for several location-bearing endpoints. Gateway audit logging is best effort until its HTTP-action mapping is corrected. The gateway is not included as a Compose service by default, and Caddy does not route `/api/*` to port `8099` without additional deployment configuration.

## Recommended Approach By Partner Type

| Partner type | Recommended approach | Why |
|---|---|---|
| Internal operations | Directus dashboard | Existing authenticated roles and governed records |
| Investor or funder | Metabase public-safe dashboard | BI views, evidence context, and controlled embedding |
| NGO or auditor | Metabase plus evidence-gap views | Reviewable aggregates and audit context |
| White-label reseller | Custom React app with backend authorization | Full presentation control without exposing privileged tokens |
| Research partner | Custom app or controlled Metabase workspace | Specialized analysis with explicit data-sharing scope |
| Backend integration | Gateway or Directus API with scoped credentials | Machine-readable access and explicit route policy |

## Security Checklist

- Load secrets with `scripts/load-secrets.sh`; never place secrets in source or URLs.
- Keep PostgreSQL, ClickHouse, Directus, and Metabase private unless an explicit deployment override is reviewed.
- Use service names such as `database` and `metabase` for Compose-internal connections.
- Use short-lived signed Metabase tokens generated by a trusted backend.
- Review Caddy frame and content-security headers before enabling iframes.
- Enforce partner scope through Directus/Metabase/gateway policy, not client-side filters.
- Verify public-safe views, evidence maturity, consent, and lifecycle status before sharing.
- Treat gateway audit records as best effort under the current implementation.
- Review partner access and permissions periodically and revoke unused credentials.

## References And Verification

- Dashboard asset index: `dashboards/metabase/README.md`
- Dashboard registry schema: `schemas/postgres/007_modeled_outputs.sql`
- Dashboard lifecycle roles: `extensions/kokonut-hooks/src/workflow.ts`
- Dashboard dataset permissions: `config/directus/permissions.sql`
- Dataset refresh engine: `services/export/dataset_refresh.py`
- Dashboard refresh seed: `schemas/seeds/050_scheduled_tasks.sql`
- Core dataset seed: `schemas/seeds/017_dashboard_datasets.sql`
- EBF dataset seeds: `schemas/seeds/033_ebf_dashboard_datasets.sql` and `034_ebf_p2_dashboard_datasets.sql`
- Caddy routes and headers: `config/caddy/Caddyfile`
- Gateway auth and deployment boundaries: `docs/gateway.md`
- EBF dashboard checks: `tests/test_ebf_dashboard.py`

Run the focused dashboard check with:

```bash
python3 -m pytest tests/test_ebf_dashboard.py -v
```
