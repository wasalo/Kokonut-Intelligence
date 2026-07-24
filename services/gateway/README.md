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

Field Collector: `https://localhost/mobile` (or `https://<lan-ip>/mobile` on the LAN).

## Modules

- `app` — Gateway application — FastAPI app with auth, routing, rate limiting, and audit.
- `audit` — Gateway audit — request logging.
- `auth` — Gateway auth — unified authentication (API key, capability token, session).
- `cli` — CLI for the API gateway.
- `rate_limiter` — Gateway rate limiter — per-caller token bucket rate limiting.
- `router` — Gateway router — route definitions and backend proxying.

## Files

6 Python modules
