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

Emergency response aggregates are available to authorized operators at
`GET /operator/api/emergency-response/{location_id}/summary` with the
location-specific `emergency_response:read` grant. The read-only response
contains counts, recovery/deadline measures, affected-area and financial
aggregates; it excludes incident descriptions, actions, support notes, lessons,
and individual incident rows.

Stored Celo attestation metadata can be read at
`GET /operator/api/attestations/{location_id}` with the location-specific
`attestation:read` grant. The route excludes claim payloads, evidence references,
and review notes. It reports persisted database state and does not verify a
live EAS contract or chain result.

Location ecocredit batches are available at
`GET /operator/api/ecocredits/{location_id}/batches` with the location-specific
`ecocredit:read` grant. The read-only response separates batch quantities from
aggregated tradable, retired, and escrowed ledger totals, preserves four-decimal
precision, and omits wallet addresses and account-level balances. It does not
issue, transfer, retire, or verify credits.

## Modules

- `app` — Gateway application — FastAPI app with auth, routing, rate limiting, and audit.
- `attestations` and `attestation_routes` — scoped metadata reads for location EAS proofs.
- `ecocredits` and `ecocredit_routes` — location-scoped batch and aggregate ledger reads.
- `audit` — Gateway audit — request logging.
- `auth` — Gateway auth — unified authentication (API key, capability token, session).
- `cli` — CLI for the API gateway.
- `operator_auth` — OIDC operator sessions, scope policies, and protected operator routes.
- `emergency_response` and `emergency_response_routes` — scoped emergency aggregates.
- `rate_limiter` — Gateway rate limiter — per-caller token bucket rate limiting.
- `router` — Gateway router — route definitions and backend proxying.
- `true_cost` and `true_cost_routes` — tenant-scoped aggregate true-cost reads.

## Files

Python modules are organized by route, identity, audit, and domain service under this package.
