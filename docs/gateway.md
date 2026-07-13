# Gateway

The FastAPI gateway is an authenticated application boundary, not a database exposure mechanism.

```text
request -> public-route lookup -> rate limit -> auth if protected -> handler -> audit
unknown route -------------------------------> protected by default
```

## Run And Check

```bash
python3 -m services.gateway --serve --port 8099
python3 -m services.gateway --health
curl http://localhost:8099/health
```

## Access Policy

Public access is an explicit allowlist in `services/gateway/router.py`. It currently covers selected `GET` routes for locations, metrics, CRISP, analytics summary, IRI resolution, federation nodes, drivers, and service health. `/`, `/health`, `/docs`, and `/openapi.json` are also intentionally public. The data-stream write route is protected.

The current metrics route calls `compute_all` and therefore creates and returns draft, unverified results. Treat it as computation output, not verified publication; governed public summaries must still use verified metric views described in [Metric Verification](metric-verification.md).

Any method/path not matching an allowlisted public policy is default-deny and requires credentials, even if a FastAPI route is later added. Protected requests may use:

- `x-capability-token`: verified against the route's exact `resource`, `action`, and optional `location_id`.
- `x-api-key`: matched against runtime keys from `DIRECTUS_ADMIN_TOKEN`, `GRPC_API_KEY`, or `KOKONUT_API_KEYS` (`key:name` entries).

Capability tokens are checked before API keys. An invalid supplied capability token is rejected rather than falling through to an API key. Never place keys in source or logs.

## Failure Behavior

- Missing or invalid protected credentials return `401` and a denied audit record.
- Rate limits return `429`.
- Directus proxy failures return `502`; internal handler failures return a generic `500` while details go to service logs.
- Successful and application-error responses are audited with caller, route, duration, and status. The four discovery/health paths bypass gateway audit middleware.

Route authors define policy metadata; security operators issue API keys or capability tokens; callers receive only the least capability required. Adding a handler does not make it public: public exposure requires an explicit policy review. See [Platform Integrity](platform-integrity.md) and [Scheduler and Events](scheduler-and-events.md).
