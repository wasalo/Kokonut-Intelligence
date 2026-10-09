# Gateway

The FastAPI gateway is an authenticated application boundary, not a database
exposure mechanism. It applies an explicit public-route policy, capability/API-key
authentication, a process-local rate limiter, and best-effort request auditing
before dispatching handlers.

The gateway is separate from Directus. Base Compose defines a `gateway` service
(loopback host port `8099`) and Caddy reverse-proxies `/mobile*` and
`/api/mobile/*` to it so the Field Collector works on the LAN. Other `/api/*`
gateway routes are not proxied by Caddy; reach them on `http://127.0.0.1:8099`
or add an explicit route when exposing them externally.

## Request Flow

```text
path bypass check
  → rate limit
  → exact method/path policy
  → capability token, if supplied
  → API key, if no capability token supplied
  → handler
  → best-effort service/durable audit

unknown method/path → protected fallback policy → usually 401 before 404
```

## Run And Check

```bash
# Compose (preferred)
docker compose up -d gateway
curl http://127.0.0.1:8099/health
curl -k https://localhost/mobile

# Host process fallback
python3 -m services.gateway.cli --serve --port 8099
curl http://localhost:8099/health
python3 -m services.gateway.cli --health
```

`--serve` starts Uvicorn on `0.0.0.0`; the default port is `8099`. Compose binds
that port to loopback only; LAN devices should use Caddy (`/mobile`,
`/api/mobile/*`). The CLI `--health` command runs
`services.core.health.overall_health()` locally. It does not make an HTTP request
to `http://localhost:8099/health`.

The HTTP application exposes:

- `GET /health`
- `GET /`
- `GET /mobile` (Field Collector HTML)
- FastAPI `GET /docs`
- FastAPI `GET /openapi.json`
- policy-controlled routes under `/api`, including `/api/mobile/*`

## Exact Route Policy

The public policy is defined in `services/gateway/router.py`.

| Method | Path | Resource/action | Public |
|--------|------|----------------|--------|
| GET | `/mobile` | `mobile_app:read` | Yes |
| GET | `/api/mobile/app` | `mobile_app:read` | Yes |
| GET | `/api/mobile/forms` | `mobile_form:read` | Yes |
| POST | `/api/mobile/register` | `mobile_device:register` | Yes |
| POST | `/api/mobile/sync` | `offline_collection:write` | Yes (device token) |
| GET | `/api/mobile/sync/status` | `offline_collection:read` | Yes (device token) |
| GET | `/api/locations` | `location:read` | Yes |
| GET | `/api/locations/{location_id}` | `location:read` | Yes |
| GET | `/api/metrics/{location_id}` | `metric:read` | Yes |
| GET | `/api/crisp/{location_id}` | `crisp_risk_assessment:read` | Yes |
| GET | `/api/analytics/{location_id}/summary` | `analytics:read` | Yes |
| GET | `/api/iri/resolve` | `iri:read` | Yes |
| GET | `/api/federation/nodes` | `federation_node:read` | Yes |
| GET | `/api/drivers` | `driver:read` | Yes |
| GET | `/api/health/services` | `service_health:read` | Yes |
| POST | `/api/data-stream/post` | `data_stream_post:create` | No |

Any method/path not matching an explicit policy receives a protected fallback
policy with resource `gateway`, action equal to the lowercase HTTP method, and
`public = false`. Adding a FastAPI handler does not make it public.

### Path Details

- `/api/locations/{location_id}` validates UUID syntax and returns `400` for an
  invalid identifier.
- Other location handlers do not perform the same local UUID validation.
- `/api/iri/resolve` requires the `iri` query parameter; FastAPI returns `422`
  when it is missing.
- `/api/data-stream/post` reads `location_id` from JSON but currently passes no
  location scope into the route authorization policy. Malformed body access can
  become a generic `500` rather than a structured validation response.

## Public Bypass Paths

The gateway middleware bypasses authentication, rate limiting, and gateway audit
for these exact paths:

```text
/
/health
/docs
/openapi.json
```

The bypass is path-based rather than method-specific. FastAPI still determines
whether the requested method/path is a valid application route after middleware
has bypassed its checks.

## Metrics Route

`GET /api/metrics/{location_id}` reads from `v_public_metric_summary`. It does
not call `compute_all`, create metric rows, or return draft computations. Its
results depend on the public metric view's requirements, including verified
metric values, active definitions/locations, and registry eligibility.

Treat this route as a read of governed public metric output. Computation remains
a separate operation and produces draft, unverified values until a human
verification step occurs.

## Authentication

### Accepted Headers

Capability tokens:

- `x-capability-token`
- `capability-token` compatibility alias

API keys:

- `x-api-key`
- `api-key` compatibility alias

Never place credentials in source code, request logs, or documentation examples.

### Precedence

Authentication order is:

1. If a capability token is supplied, verify it.
2. If no capability token was supplied, verify an API key.
3. If neither exists, reject protected access.

An invalid supplied capability token does not fall through to an API key.

### API Keys

The gateway reads environment variables at request time:

- `DIRECTUS_ADMIN_TOKEN`
- `GRPC_API_KEY`
- `KOKONUT_API_KEYS`
- `KOKONUT_API_KEY_SCOPES`

`KOKONUT_API_KEYS` uses:

```text
key:name,key:name
```

`KOKONUT_API_KEY_SCOPES` uses:

```text
name:resource:action,name:resource:action
```

Supported wildcard examples:

```text
service:*:read
service:resource:*
service:*:*
```

`DIRECTUS_ADMIN_TOKEN` is treated as a full-access gateway admin key. A
`GRPC_API_KEY` is not automatically privileged; it is denied unless its
resolved name has appropriate scopes. Custom keys fail closed when no matching
scope is configured. Key comparisons use constant-time matching.

The PostgreSQL `api_key` table exists, but the gateway does not consult it.
Gateway authentication is environment-backed rather than database-managed.

### Capability Tokens

Capability tokens are stored in `capability_token` from
`schemas/postgres/121_capability_tokens.sql`. They support:

- SHA-256 token hashing;
- holder identity;
- JSONB resource/action capabilities;
- expiration;
- revocation;
- maximum usage;
- atomic usage counting;
- optional metadata.

Verification checks token existence, revocation, expiration, resource/action,
location constraints when provided, and maximum usage.

## Location Scoping

The route policy can include an optional `location_id`, but current propagation
is incomplete:

- `/api/locations/{location_id}` supplies its route UUID to policy checks.
- `/api/metrics/{location_id}` currently passes `None` to the policy.
- `/api/crisp/{location_id}` currently passes `None` to the policy.
- `/api/analytics/{location_id}/summary` currently passes `None` to policy.
- `/api/data-stream/post` does not use the request body's location for policy.

Capability matching can also allow an unscoped capability to satisfy a request
that could otherwise have a location scope. Do not describe the current gateway
as providing strict end-to-end location authorization for every location route.
Correct this implementation before treating location scope as a security
guarantee.

## Rate Limiting

The gateway uses an in-memory token bucket:

| Setting | Value |
|---------|-------|
| Bucket capacity | 100 tokens |
| Refill rate | 10 tokens/second |
| Cost | 1 token/request |
| Persistence | None; process-local |
| `Retry-After` | Not emitted |

Rate-limit identity is the `x-api-key` value when present, otherwise client IP.
The `api-key` alias is not used for rate-limit identity. Capability-token callers
without `x-api-key` are grouped by IP. Multiple gateway processes have separate
buckets, and state disappears on restart.

Rate-limited requests return:

```json
{"error": "Rate limit exceeded"}
```

with HTTP `429`. Rate-limited requests are not gateway-audited. Directus rate
limiting settings in Compose are separate and do not configure this gateway
bucket.

## Audit Behavior

The gateway attempts to record caller, route, method, IP, user agent, duration,
response status, and failure reason. It also emits service logs.

The intended durable table is `access_audit_log`, whose allowed actions are:

```text
read, write, attest, publish, delete, admin
```

### Current Durability Limitation

`GatewayAudit.log()` currently passes HTTP verbs such as `get` and `post` as the
database action. Those values violate the durable table constraint. The insert
failure is swallowed. Therefore:

- service-level gateway logging is emitted;
- durable `access_audit_log` rows are not reliable;
- application errors may be represented as `denied`, not a distinct error state;
- audit failure does not block the request.

Additionally:

- `/`, `/health`, `/docs`, and `/openapi.json` bypass gateway audit;
- `429` responses are not audited;
- uncaught middleware exceptions may not produce a request audit row;
- capability-token IDs are not consistently attached to gateway audit records;
- the gateway does not use the database `api_key` table.

Until the action mapping is corrected and tested, describe gateway auditing as
best-effort rather than a complete durable audit guarantee.

## Error Responses

| Situation | Response |
|-----------|----------|
| Missing credentials | `401`, `credentials_required` |
| Invalid capability token | `401`, `invalid_capability_token` |
| Invalid API key | `401`, `invalid_api_key` |
| API-key scope denied | `401`, `api_key_scope_denied` |
| Rate limit | `429`, `Rate limit exceeded` |
| Invalid location UUID | `400`, `Invalid location identifier` |
| Missing FastAPI query parameter | `422` validation response |
| IRI not found | `404`, `IRI not found` |
| Directus proxy failure | `502`, `Upstream service unavailable` |
| Internal handler failure | `500`, `Gateway request failed` |

The data-stream write handler has limited body validation; malformed input can
become a generic `500` rather than a structured `400`.

## Directus Proxy

Only these gateway routes proxy Directus:

- `GET /api/locations`
- `GET /api/locations/{location_id}`

The gateway uses `DIRECTUS_URL`, defaulting to `http://localhost:8055`, and
creates a new unauthenticated upstream request. It does not forward gateway
credentials, Directus bearer tokens, caller identity, or general request
headers. Upstream response bodies are wrapped as `{"data": ...}` rather than
forwarded with their original parsed status/body contract.

## Deployment Boundaries

- The base Compose stack defines the gateway on loopback port 8099; the
  production overlay removes that direct host mapping.
- Base Caddy routes `/directus/*`, `/admin/*`, `/maps/*`, and mobile-specific
  paths to the gateway; it does not route general `/api/*` traffic to port 8099.
- Metabase is excluded by default and has no route in the default Caddyfiles.
- `CORS_ORIGIN` configures Directus; the gateway does not install FastAPI CORS
  middleware.
- `PUBLIC_RESTRICT=true` configures Directus and is not read by gateway policy.
- Caddy supplies security headers only for Caddy-served traffic. Direct access
  to port 8099 does not automatically receive those headers.

If externally exposing the gateway, configure a dedicated service, TLS/reverse
proxy, CORS policy, security headers, credential injection, and network access
policy explicitly.

## Security Rules

1. Public access requires an explicit method/path policy.
2. Unknown routes remain protected by default.
3. Capability-token failure does not fall through to API-key authentication.
4. API keys and tokens must be supplied through protected runtime configuration.
5. Public metrics are reads of verified public views, not computation endpoints.
6. Least-privilege scopes should be used for service keys and capability tokens.
7. Durable audit behavior must be verified after the current action-mapping defect
   is fixed.
8. Gateway exposure requires explicit reverse-proxy and deployment review.

## Tests And References

Relevant tests:

- `tests/test_gateway_auth.py`
- `tests/test_gateway_public_metrics.py`
- `tests/test_phase3_4.py`
- `tests/test_cli.py`

Primary implementation references:

- `services/gateway/app.py`
- `services/gateway/router.py`
- `services/gateway/auth.py`
- `services/gateway/rate_limiter.py`
- `services/gateway/audit.py`
- `services/gateway/cli.py`
- `services/security/capabilities.py`
- `services/security/audit.py`
- `schemas/postgres/008_governance.sql`
- `schemas/postgres/121_capability_tokens.sql`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `config/caddy/Caddyfile`
