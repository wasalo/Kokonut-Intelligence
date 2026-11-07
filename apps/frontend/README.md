# Kokonut Intelligence Operator Control Plane

This workspace builds one authenticated React application with three lazy-loaded
route modules:

- `/ops/*` — General Operations
- `/field/*` — Field Operations and supervisor workflows
- `/governance/*` — Governance operations

The modules share one Router, operator session, navigation shell, design system,
and deployment. Their route prefixes and capability-specific screens keep each
vertical clear without requiring separate application builds or Workers. The
current React screens are partial migrations and do not claim full feature
parity or change server authorization.

The Delphi participant experience at `/participation/delphi` and encrypted,
offline Field Collector at `/api/mobile/app` remain separate clients. Their
invite/consent and device-token/offline protocols have different audiences and
security requirements; the operator bundle does not load either client.

`@kokonut/operator-client` centralizes same-origin, no-store requests to the
operator Gateway API, CSRF handling, normalized HTTP errors, request
cancellation, and shared session parsing. The Control Plane loads the session
once and exposes Gateway-backed sign-in and sign-out across route modules. The
Gateway returns a CSRF token only from the authenticated, no-store session
response after matching it to the server-side session hash; the cookie remains
scoped to `/operator`. Sign-in returns operators to the module route where they
started. Mutation retries remain the caller's responsibility and must reuse
the original request ID and unchanged payload.

## Local development

Run commands from this directory with Node.js 22.22 or newer:

```sh
npm ci
npm run dev
npm run build
```

The single Vite server serves all three production path prefixes. Gateway and
retained compatibility paths proxy to `http://127.0.0.1:8000` by default; set
`KOKONUT_GATEWAY_DEV_TARGET` to override that target. `npm run build` produces
one deployable Control Plane bundle; route modules and their CSS are split into
on-demand chunks.

This proxy makes local routing convenient. It does not substitute for trusted
HTTPS and browser identity acceptance in G4.

## Production routing and deployment

One Cloudflare Worker Static Assets deployment serves the Control Plane at
`hub.kokonut.network`. It claims `/ops` and descendants, `/field` and
descendants, `/governance` and descendants, plus the shared `/assets/*` bundle
path. SPA navigation on the three module prefixes returns the same app shell.
The Worker does not claim Gateway or compatibility routes: `/operator/*`,
`/api/mobile/*`, and `/participation/*` continue to Coolify's VPS origin.
Personalized/API/auth/media responses are never served from the static asset
cache. Do not attach a hostname-wide Worker route unless it explicitly forwards
all retained Gateway paths to the origin.

For an isolated layout and asset preview on the account's `workers.dev`
subdomain, run `npm run deploy:control-plane:preview`. This preview has no
`hub` routes and no Gateway origin; its same-origin API calls do not provide
identity acceptance. It is a visual preview of the static shell only.

After G4 approves the trusted origin and Cloudflare credentials are provisioned,
deploy the production route with:

```sh
npm run deploy:control-plane
```

The command builds the Control Plane and deploys the Worker configured in
`apps/control-plane/wrangler.jsonc`. It does not create DNS records, configure
ZITADEL, R2, or the Coolify Gateway origin. Keep Cloudflare credentials in the
operator's environment or secret store; do not add them to this workspace. Do
not deploy this shell as a production replacement for the existing operator,
Delphi participant, or Field Collector workflows before parity acceptance.

Cloudflare Worker Routes execute only for proxied (orange-cloud) DNS records.
Keep the current `hub` record unchanged while validating the candidate; proxy
the `hub` record to the candidate origin only as part of the reviewed cutover.
The static Worker routes cover only the three frontend modules and `/assets/*`,
so unmatched Gateway and compatibility paths continue to the VPS origin.
