# Kokonut Gateway

The FastAPI Gateway is the native application boundary between clients and
Kokonut's domain services. It does not expose PostgreSQL directly. Its route
classes use distinct identity and authorization mechanisms; a route being
registered does not imply that it is public or that every tenant boundary has
passed release acceptance.

The Gateway is part of the Kernel base. Directus, ClickHouse, gRPC, and Caddy
are optional adapters. The legacy Compose bundle also contains a Gateway
service, but the isolated candidate is defined by
`docker-compose.kernel-candidate.yml`; see [deployment](deployment.md) and the
[current refactor status](refactor/current-state-and-implementation.md).

## Route classes and identity

| Route class | Example prefix | Identity/authorization |
|---|---|---|
| Explicit public read routes | `/api/locations`, `/api/metrics/{location_id}` | Only exact method/path policies marked public; unknown routes remain protected |
| API-key/capability routes | Other protected `/api/*` operations | `x-api-key` or `api-key`, or `x-capability-token` / its compatibility alias; route scopes and location are checked where defined |
| Field Collector | `/api/mobile/*` | Public bootstrap routes, single-use enrollment, opaque device credentials, and location-scoped collection/review flows as specified per route |
| Delphi participant | `/api/participation/delphi/*` | Participant capability/session tokens; this identity is separate from an operator |
| Browser operator console | `/operator/api/*` | Optional OIDC login, database-backed opaque `kokonut_operator_session` cookie, explicit org/location grants, CSRF token on mutations, and private/no-store responses |
| OIDC authentication | `/operator/auth/*` | Login/callback/session/logout route-specific policy; HTTPS origin required for secure cookies |

The Gateway's OIDC provider is optional. When enabled, the operator's identity
comes from the configured OIDC issuer; Kokonut stores opaque session-token
hashes, provisions grants separately, and checks those grants before
location-scoped operations. The self-hosted ZITADEL Compose profile is optional
and selected separately. Provider credentials must be supplied through the
approved encrypted secret path. The presence of a client or Compose overlay is
not evidence of a live configured provider.

For browser mutations, the caller must send the CSRF token in the
`X-CSRF-Token` header matching the CSRF cookie. The operator session cookie is
Secure, HttpOnly, and scoped to `/operator`; frontend origins must be explicitly
configured. Do not treat API keys, participant credentials, device tokens, and
operator sessions as interchangeable identities.

## Request policy

The public-route allowlist and API-key policies are maintained in
`services/gateway/router.py` and related route modules. The OIDC session policy
is defined in `services/gateway/operator_auth.py`. Middleware applies rate
limiting, request/location policy, authentication, mutation-audit reservation,
handler dispatch, and audit recording. A route without an explicit policy
falls through to protected access. Public `/health`, root, FastAPI docs, and
OpenAPI discovery do not make the application data routes public.

The data-stream create route is an example of the strict path: request shape is
validated before service access, its declared `location_id` is used for
authorization, a new post is draft-only, and private errors are sanitized with
`Cache-Control: no-store`. Other API and operator routes have their own exact
contracts and should be reviewed in code/OpenAPI rather than inferred from this
example.

`GET /api/metrics/{location_id}` reads governed public metric output; it does
not compute or verify metrics. Metric computation writes draft, unverified
values until a human reviewer completes the separate verification workflow.

## Run and check

For the isolated candidate, use the profile planner and explicit project name:

```bash
source scripts/load-secrets.sh
python3 scripts/kernel-profile.py minimal --project kokonut-kernel-dev --action config
python3 scripts/kernel-profile.py minimal --project kokonut-kernel-dev --action up
```

Both planner calls print commands only. Inspect the output, apply the candidate
schema with the correct Compose project/file, then execute the reviewed startup
command. The app's default loopback health URL is
`http://127.0.0.1:8098/health`. For OIDC browser routes, select the proxy and
OIDC overlays and use a trusted HTTPS origin. The planner does not configure an
OIDC provider, migrate the database, or certify a profile.

The legacy stack's Gateway service binds loopback port `8099` by default. The
host command `python3 -m services.gateway.cli --serve --port 8099` starts
Uvicorn on `0.0.0.0`; do not use that host-process mode on an untrusted network
without an explicit ingress, firewall, TLS, and authorization plan. The CLI
`--health` operation evaluates local component health; it is not an HTTP request
to the running server.

## API-key and capability-token authentication

The legacy `/api` policy accepts:

- API keys: `x-api-key` or `api-key`.
- Capability tokens: `x-capability-token` or `capability-token`.

If a capability token is supplied it is checked first; an invalid token does
not fall through to an API key. Custom API keys require configured resource and
action scopes. Location-specific scopes can include an explicit location ID;
`KOKONUT_STRICT_LOCATION_SCOPE=true` requires a protected location-specific
request to match a location-qualified scope. Avoid the all-powerful legacy
Directus admin token outside a dedicated compatibility boundary.

Capability tokens store a token hash, holder, resource/action capabilities,
expiration, revocation, maximum usage, and optional metadata. A successful
capability check uses the request's location context where supplied. It is a
separate mechanism from OIDC operator grants and mobile device enrollment.

## Location authorization and database boundary

Many routes carry a canonical `location_id`; browser operator operations also
require an active owner/share grant. Supported tenant reads and writes establish
the matching signed PostgreSQL context on the transaction that performs the
query or write. The rollout is still closing remaining runtime/direct-database,
Directus, and downstream-consumer boundaries. Do not claim universal tenant
isolation or enable broad RLS based only on the Gateway check; use the current
[C1 ACL closure plan](refactor/c1-runtime-acl-closure-plan.md) and refactor
status for the reviewed scope.

## Rate limiting

The limiter is a replaceable interface selected by
`KOKONUT_RATE_LIMIT_PROVIDER`:

- `local` uses a process-local token bucket (100-token capacity, 10 tokens per
  second by default). Its state disappears on restart and is not shared across
  API replicas.
- `postgres` uses the shared database-backed limiter for processes targeting
  the same database.

The candidate base defaults to `local`; the Standard overlay defaults to
`postgres`. A configured backend failure returns `503` rather than silently
downgrading. The selected provider and multi-process behavior must match the
deployment profile.

## Audit and failure behavior

Gateway audit events are written to the database when available. A failed DB
write is retained in a bounded local SQLite journal for replay. The candidate
Compose manifest stores this journal on its dedicated volume and starts a
bounded replay loop. Mutation requests reserve journal capacity before dispatch
and fail closed when the audit journal is unavailable or has reached its write
restriction threshold. Monitor `/health`'s `audit_capture` field and the
configured spool thresholds; a healthy HTTP liveness response alone does not
mean every provider or worker is ready.

The local journal is durable only within its deployment volume. Include it in
backup/recovery policy, protect access to it, and check replay backlog during
recovery. Public health, discovery, and rate-limited responses have distinct
audit behavior. Audit storage must not be described as a substitute for an
operator audit or human approval record.

## CORS, ingress, and caching

- `KOKONUT_GATEWAY_CORS_ORIGINS` is an explicit comma-separated origin allowlist
  and defaults to empty. Wildcards are ignored. Cookie-authenticated requests
  need a precise HTTPS origin and successful preflight/credentialed-response
  verification.
- The candidate Caddy overlay is optional and binds to loopback ports `8088`
  and `8448` by default. Public binds require a deliberate domain, certificate,
  trusted-proxy, CORS, and firewall configuration.
- Protected/private routes set no-store headers according to route contracts;
  do not add caching at a proxy for operator, evidence, enrollment, or review
  responses.
- The legacy Directus CORS variable is separate from Gateway CORS.

## References

- `services/gateway/app.py` — application/middleware and session integration.
- `services/gateway/router.py` — legacy API policies and route contracts.
- `services/gateway/operator_auth.py` — OIDC/session/grant policy.
- `services/gateway/audit.py` and `services/gateway/audit_spool.py` — audit and
  bounded replay journal.
- `services/gateway/rate_limit_backend.py` — replaceable rate limiter contract.
- `schemas/postgres/` — checksummed schema and authorization migrations.
- `docker-compose.kernel-candidate.yml` and selected optional overlays.
- [Field Collector guide](refactor/mobile-access-contract.md) for collection-specific
  identity, consent, offline queue, and review boundaries.
