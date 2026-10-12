# Optional Kernel Caddy ingress

`docker-compose.kernel-proxy.yml` adds the repository's pinned Caddy image to
the standalone candidate, with optional standard role separation. Its dedicated
`config/caddy/Caddyfile.kernel` forwards every path unchanged to `app:8099`.
The gateway retains route policy, unknown-route protection, mobile handlers,
and CORS configuration. There is no Directus fallback, static private-media
mount, gRPC forwarding, or credential logging configuration in this proxy.
Legacy Caddy manifests and configuration remain available for legacy recovery.

Defaults are domain localhost, loopback bind, HTTP 8088 and HTTPS 8448. Local
certificate trust is provided by Caddy's local CA and is not automatically
trusted by browsers or clients. The overlay does not install a trusted CA in
the host trust store. HTTP explicitly redirects to the configured HTTPS host
port (`KOKONUT_KERNEL_HTTPS_PORT`, default `8448`), including when HTTPS is
published on a nonstandard local port. Certificate state uses distinct
candidate volumes.

## Deployment contract

- `proxy` is a separate opt-in Compose service using the digest-pinned Caddy
  image. It waits for the candidate `app` healthcheck and forwards all HTTP
  paths to `app:8099`; it does not route directly to PostgreSQL, Directus,
  Metabase, MQTT, the standalone sensor receiver, or gRPC.
- Default host bindings are `127.0.0.1:8088` and `127.0.0.1:8448`. Setting
  `KOKONUT_KERNEL_PROXY_BIND` to a non-loopback address changes this into
  network ingress and requires a separately reviewed domain, TLS, DNS, host
  firewall, and authentication policy.
- Local HTTPS uses Caddy's local CA and stores certificate state in dedicated
  candidate volumes. The profile does not install that CA in host/browser trust
  stores. Public-domain certificate acquisition and recovery are not certified.
- HTTP redirects to HTTPS using the configured host HTTPS port. The proxy adds
  three response security headers. Gateway authorization, CORS, rate limits,
  audit and request-size policies remain owned by the application.
- Compose defines no proxy healthcheck. The recorded HTTP/TLS probes verify the
  path through Caddy and the gateway, but do not create a persistent ingress
  readiness signal.
- The gateway ignores forwarded headers by default. Audit and IP-based limits
  therefore see Caddy's peer address; do not enable broad proxy trust to recover
  per-client addresses. Multi-hop trust and public-origin behavior remain open.

Compose selection after acceptance:

```sh
docker compose -p kokonut-kernel-candidate \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-standard.yml \
  -f docker-compose.kernel-proxy.yml up -d --build
```

Load encrypted secrets first as documented in the standard profile. Apply
scheduler migration 371 before deploying its worker role. Public deployment
requires an explicitly selected domain, bind address, reachable TLS ports,
DNS, and certificate validation. Keep the API's direct host port on loopback.
An external ingress can replace Caddy by omitting this overlay and forwarding
the same paths to the gateway through a reviewed private network.

## Forwarding boundary

The gateway CLI now explicitly sets Uvicorn `proxy_headers=False`. Requests
retain the socket peer for audit and IP-based rate limits, regardless of
forwarded headers or inherited forwarding environment. Behind Caddy that peer
is the proxy: unauthenticated requests share its process-local IP limit.
Credential-based caller identities remain distinct. This conservative setting
also applies to legacy deployments invoking the gateway CLI; review that
behavior during cutover. It does not change route authorization.

A single-hop runtime probe sent forged `X-Forwarded-For`, `X-Real-IP`, and
`Forwarded` values through Caddy to a unique unknown route. The route returned
401, and the one matching `access_audit_log` row recorded the Caddy container's
network address rather than any supplied address. That synthetic denied audit
row intentionally remains in the candidate database. [Probe evidence](builds/2026-10-10-recovery/proxy-forwarded-header-audit.json).

A narrowly scoped trusted-proxy policy remains future work. Do not enable
wildcard forwarding trust to obtain individual client IPs. Application-generated
absolute URL generation, secure-cookie behavior, and public-origin handling
need acceptance checks because the upstream connection uses HTTP. The configured
proxy redirect has a separate loopback acceptance result below.
Multiple API replicas still require a shared rate-limit implementation before
scale certification. No public readiness claim is made by this overlay.

## Isolated localhost runtime check

On 10 October 2026, the pinned Caddy image passed `caddy validate` and served
the existing healthy Kernel candidate app over an internal Docker network. The
client trusted the Caddy local root CA explicitly and verified the `localhost`
certificate hostname. HTTPS `GET /health` returned 200; HTTP returned 308 to
`https://localhost/health`; the configured `X-Content-Type-Options`,
`X-Frame-Options`, and `Referrer-Policy` headers were present. An unauthenticated
unknown path returned 401, preserving the gateway's fail-closed route policy.
The certificate remained usable after Caddy container recreation with its data
volume retained.

The final proxy container had no published host ports. Its upstream connection
used the existing `kokonut-kernel-candidate_kernel` network, while the probe
client used a separate internal-only verification network. The pre-existing
candidate app retained its loopback `127.0.0.1:8098` binding; that app and its
database were not rebuilt or restarted. The legacy stack stayed stopped. Normal gateway
access auditing ran for the HTTPS requests; no farm or sensor domain writes or
migrations were issued. The scoped result is in
[`kernel-proxy-runtime.json`](builds/2026-10-10-recovery/kernel-proxy-runtime.json).

The first temporary Compose override used `ports: []`, which Compose merged with
the default loopback publications. That proxy was stopped before any probe
traffic. The resolved configuration was corrected with `!reset []`, checked to
have no host bindings, and then used for all runtime requests. The nonfatal
`caddy validate` output also reported that the source Caddyfile is not formatted.

That private-network run did not validate host-published ingress, public
DNS/ACME, OS/browser CA trust, mobile or upload routes, CORS, rate limits,
forwarded-header trust across other ingress providers or multiple proxy hops,
or production origin/cookie behavior. Those remain required before selecting
a public deployment profile.

## Loopback-published host ingress

The next isolated check exposed a redirect defect in the prior configuration:
HTTP on the default host port redirected to `https://localhost/health`, which
omitted the published HTTPS port `8448`. The Caddyfile now constructs the
redirect from `KOKONUT_KERNEL_HTTPS_PORT`, and the proxy overlay passes that
setting to Caddy. The port remains configurable for local deployments.

On 10 October 2026, the pinned proxy was published only on
`127.0.0.1:8088` and `127.0.0.1:8448`. A host request to
`http://localhost:8088/health` returned 308 with
`Location: https://localhost:8448/health`; following the redirect with the
local CA explicitly trusted and the `localhost` hostname verified returned
200 from the existing candidate app. The request used one redirect. The
resolved container port bindings were both loopback-only. [Runtime evidence](builds/2026-10-10-recovery/proxy-loopback-ingress.json).

A separate temporary Compose project used HTTP `18088` and HTTPS `18448`. The
resolved Compose binding and Caddy redirect agreed: HTTP returned 308 to
`https://localhost:18448/health`, and following it with the local CA trusted
and hostname verification enabled returned 200. This confirms the HTTPS port
override controls both host publication and the redirect target. [Alternate-port evidence](builds/2026-10-10-recovery/proxy-custom-port.json).

The temporary proxy reused the healthy candidate app and did not rebuild or
restart it or its database. The legacy stack remained stopped. The health
request traversed normal gateway middleware; audit persistence was not queried.
No farm or sensor domain writes or migrations were issued. The disposable
proxy project and its volumes were removed after the check. No pytest suite ran.

This verifies loopback-published ingress only. It does not validate a
non-loopback/public bind, public DNS/ACME, browser/OS trust installation,
mobile/upload paths, CORS, rate limits, multiple trusted proxy hops, or
production origin/cookie behavior. Those remain required before a public
deployment profile is selected.

## CORS preflight check

The candidate gateway's active `CORS_ORIGIN` contains four explicit localhost
origins. A direct loopback preflight for `http://localhost:3000`, method `GET`,
and header `x-api-key` returned 200 with the same origin in
`Access-Control-Allow-Origin`; the response allowed both the requested method
and header. The same preflight from `https://untrusted.invalid` returned 400
without `Access-Control-Allow-Origin`. [Evidence](builds/2026-10-10-recovery/proxy-cors-preflight.json).

These were `OPTIONS` requests directly to the gateway, not through Caddy. The
gateway middleware short-circuits `OPTIONS`, and CORS handles preflight before
the route. A separate `GET /health` confirmed the endpoint and traversed normal
gateway middleware; audit persistence for that health request was not queried.
No farm or sensor domain data or schema changed.

A follow-up sent two unauthenticated GETs to one unique unknown path. Both
returned 401. The configured origin received `Access-Control-Allow-Origin` on
the error response; the untrusted origin did not. A read-only exact-path query
found the two expected denied audit rows (`credentials_required`), which remain
in the candidate database. [Evidence](builds/2026-10-10-recovery/proxy-cors-auth-response.json).
This does not check successful authenticated responses, mutation responses,
credentialed browser requests, mobile/private-media paths, or public origins.

## Isolated source-level rate-limit middleware check

At the time of this source-path check, the active candidate image predates
`services/gateway/rate_limit_backend.py`, so importing the current limiter
integration into that running container failed.
To check current source without rebuilding or touching the candidate stack, a
disposable container ran with networking disabled, the current workspace's
`services/` mounted read-only, and `GatewayAudit.log` replaced by an in-memory
capture. The ASGI app received an injected local limiter configured with a
one-token test bucket and a 0.01-token/second refill; this is deliberately not
the configured production default.

The first `/health` GET returned 200 and used the test token. A configured-origin
OPTIONS preflight then returned 200 despite the exhausted bucket, showing that
preflight bypassed token consumption. The next GET returned 429 with
`Retry-After: 100`; the configured origin's allow-origin header was present on
that throttled response. The in-memory audit capture contained one allowed 200
and one denied 429 (`rate_limited`). [Sanitized evidence](builds/2026-10-10-recovery/gateway-rate-limit-isolated.json).

This establishes only the current-source ASGI middleware path under an injected
test policy. It does not establish candidate runtime behavior, real default
settings, persisted audit behavior, PostgreSQL shared-provider semantics,
concurrency, restart/eviction behavior, or multi-replica limits. No candidate
app/database, domain data, migration, or persistent audit was touched; the
disposable container was removed. No pytest suite ran. The later deployed local
runtime check below covers the candidate image/default local path and persisted
audit, but the other provider/concurrency/restart limitations remain.

## Rebuilt local limiter runtime check

The candidate app image was rebuilt as
`sha256:65827b0ffbb2b30d8a979006a81216660ba2915922118adb8d0aa0a877c20b10`.
Before replacing the active app, an API-only canary used that image on
`127.0.0.1:18098`, connected to the existing private candidate database, with
`KOKONUT_RATE_LIMIT_PROVIDER=local` and the configured localhost CORS origins.
The current source defaults are 100 bucket tokens and 10 tokens/second refill.

A sequential loopback burst of 127 `GET /health` requests completed in 2.766
seconds before the first 429. That response had `Retry-After: 1` and
`Access-Control-Allow-Origin: http://localhost:3000`. An OPTIONS preflight from
that origin returned 200 after the bucket was exhausted; the following GET was
again denied with 429. The 127 allowed and two denied rows for the exact probe
user-agent were confirmed by a read-only audit query and intentionally remain
in the candidate database. [Runtime evidence](builds/2026-10-10-recovery/gateway-rate-limit-runtime.json).

The rebuilt image was then promoted to the active candidate app. It is healthy
on `127.0.0.1:8098`, its configured provider is `local`, and a post-promotion
health request returned 200 with the configured CORS header. Only the app
container was recreated; the database container stayed running and its volume
was untouched. The canary container was removed. The old app filesystem was
saved as a local rollback image before replacement; no container environment
or database volume was included. Its image tag and restore command are in the
evidence record.

One earlier exploratory burst and one header-inspection request also created
synthetic audit rows; their counts and user agents are listed in the evidence.
They remain as security audit history. The first canary launch failed before
serving traffic because its manual environment omitted the `PG_PASSWORD` alias;
the corrected launch mirrored Compose. No domain writes or migrations occurred.
No pytest suite ran. This accepts the local single-process runtime path, not
PostgreSQL shared limits, concurrent correctness, restart/eviction policy,
multi-replica limits, or public ingress.

## Evidence and rollback

Compose parsing with placeholder secrets, Caddy runtime configuration validation,
the internal TLS/redirect/header/unknown-route smoke, loopback-published
HTTP-to-HTTPS redirect and followed TLS health request, one-hop
forwarded-header spoofing/audit identity check, alternate HTTPS-port override,
configured/untrusted CORS preflight, allowlisted-origin CORS decoration on an
authentication denial, and a deployed local limiter burst with durable audit
evidence passed. The local provider is now deployed in the candidate image;
shared PostgreSQL limits and scale behavior remain unverified. No pytest suite
was added or run. Mobile routing, broader authorization parity, multi-hop
trusted-proxy policy, normal-response and credentialed CORS behavior,
concurrent/shared rate-limit behavior, non-loopback/public ingress, and
production certificate recovery remain pending.

Rollback stops/removes only the candidate proxy and omits its overlay; retain
certificate volumes. Omitting the file alone leaves an orphan proxy running.
The candidate's loopback API remains the local access path. Restore a previous
gateway image only after reviewing its forwarding trust behavior; never alter
database volumes or migration history for proxy rollback.
