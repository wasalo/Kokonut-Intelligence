# gateway

`services.gateway` — Unified API Gateway — single entry point for all API traffic.

## CLI Usage

```bash
python3 -m services.gateway.cli --help
```

## Modules

- `app` — Gateway application — FastAPI app with auth, routing, rate limiting, and audit.
- `audit` — Gateway audit — request logging.
- `auth` — Gateway auth — unified authentication (API key, capability token, session).
- `cli` — CLI for the API gateway.
- `rate_limiter` — Gateway rate limiter — per-caller token bucket rate limiting.
- `router` — Gateway router — route definitions and backend proxying.

## Files

6 Python modules
