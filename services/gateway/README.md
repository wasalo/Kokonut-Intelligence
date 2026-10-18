# gateway

`services.gateway` — Unified API Gateway — single entry point for all API traffic.

## Run

```bash
# Compose (preferred; Caddy proxies /mobile and /api/mobile/*)
docker compose up -d gateway

# Host process
python3 -m services.gateway.cli --serve --port 8099
python3 -m services.gateway.cli --help
```

Field Collector: `https://localhost/mobile/` (or `https://<lan-ip>/mobile/` on the LAN).

The OIDC operator API exposes a location-scoped, aggregate-only true-cost read
at `GET /operator/api/true-cost/{location_id}/summary`. It requires the
`true_cost_accounting:read` grant for that location and uses signed database
tenant context in a read-only transaction. It returns statement, hidden-cost,
natural/social valuation, and capital-flow summaries; it does not expose
individual worker or evidence records.

## Modules

- `app` — Gateway application — FastAPI app with auth, routing, rate limiting, and audit.
- `audit` — Gateway audit — request logging.
- `auth` — Gateway auth — unified authentication (API key, capability token, session).
- `cli` — CLI for the API gateway.
- `operator_auth` — OIDC operator sessions, scope policies, and protected operator routes.
- `rate_limiter` — Gateway rate limiter — per-caller token bucket rate limiting.
- `router` — Gateway router — route definitions and backend proxying.
- `true_cost` and `true_cost_routes` — tenant-scoped aggregate true-cost reads.

## Files

Python modules are organized by route, identity, audit, and domain service under this package.
