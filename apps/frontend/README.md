# Kokonut Intelligence Operator Control Plane

This workspace builds one React application with a public landing page and
three lazy-loaded authenticated route modules:

- `/` — public Kokonut Intelligence ecosystem overview
- `/ops/*` — General Operations
- `/field/*` — Field Operations and supervisor workflows
- `/governance/*` — Governance operations

The route modules share one Router, operator session, navigation shell, design
system, and deployment. Their route prefixes and capability-specific screens
keep each vertical clear without requiring separate application builds or
Workers. The public landing page uses explicit public Gateway projections and
does not require an operator session. It shows an empty directory when no public
locations are available; it does not invent example impact data. The authenticated
React screens remain partial migrations and do not claim full feature parity or
change server authorization.

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
scoped to `/operator`. Operator sessions last 12 hours by default so a normal
operations shift does not require repeated sign-in; deployments may configure
`KOKONUT_OPERATOR_SESSION_TTL_SECONDS` from 300 seconds to the 12-hour maximum.
The expiry remains enforced server-side. Sign-in returns operators to the
module route where they started. Mutation retries remain the caller's
responsibility and must reuse the original request ID and unchanged payload.
Shared UI tokens in `packages/ui/src/styles.css` use the Kokonut Network palette
also used by the public site.

## Location and farm workflows

`/ops/administration` can create a location and its first farm or add a farm to
an active, verified existing location owned by the selected tenant. The second
path leaves the existing location untouched and requires the farm polygon to be
inside its boundary. Both paths require an approval or internal decision
reference; they do not establish land title or import provider data.

For a new location, the representative point is entered as separate latitude
and longitude values or pasted as `latitude, longitude` from Google Maps and
applied with **Use map pin**. This point is not a boundary. Boundaries are
WGS84 GeoJSON polygons or at least three distinct perimeter pairs entered one
per line as `longitude, latitude`; a farm boundary must fit inside its location
boundary. If you have a GeoJSON Point file, copy its coordinates into the
representative-point fields; upload the Polygon file as the boundary. The form
currently has no embedded click-to-pin map; that improvement is tracked
separately in the refactor follow-ups.

`/field/records` provides a location-scoped farm-activity form. It can link an
entry to a farm, plot, crop cycle, and farm task from bounded relation choices
for the selected location. These links are optional for a location-level entry;
the Gateway and database validate parent/location consistency. Creating an
entry saves an unsubmitted draft only. Field Collector submissions use the
separate offline client and are not listed or attached by this form.

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

As of 11 November 2026, the candidate Control Plane is deployed through Cloudflare
Worker Static Assets at `hub.kokonut.network` (version
`77564893-2c14-4053-9910-0da656fb7bed`). The Worker serves `/`, `/ops` and
descendants, `/field` and descendants, `/governance` and descendants, plus
`/assets/*`. SPA navigation on those paths returns the app shell. The Worker
does not claim Gateway or compatibility routes: `/operator/*`, `/api/mobile/*`,
and `/participation/*` continue to Coolify's VPS origin. Personalized/API/auth/
media responses are not served from the static asset cache. Candidate deployment
does not mean all workflows or production acceptance gates have passed; use the
[current refactor status](../../docs/refactor/current-state-and-implementation.md).

For an isolated layout and asset preview on the account's `workers.dev`
subdomain, run `npm run deploy:control-plane:preview`. This preview has no
`hub` routes and no Gateway origin; its same-origin API calls do not provide
identity acceptance. It is a visual preview of the static shell only.

To build and deploy the configured Worker, run:

```sh
npm run deploy:control-plane
```

The command builds the Control Plane and deploys the routes in
`apps/control-plane/wrangler.jsonc`; it updates the live `hub` Worker and does
not create DNS records or configure ZITADEL, R2, or the Coolify Gateway origin.
Use `npm run deploy:control-plane:preview` for an isolated `workers.dev` visual
preview. Keep Cloudflare credentials in the operator's environment or secret
store, not in this workspace. The partial Control Plane does not replace the
legacy operator workflows, Delphi participant client, or Field Collector;
retain those paths until their own parity gates pass.

Cloudflare Worker Routes execute only for proxied (orange-cloud) DNS records.
The `hub` Worker routes are explicit, so unmatched Gateway and compatibility
paths continue to the VPS origin. Do not add a hostname-wide route unless it
preserves that forwarding behavior and keeps personalized responses uncached.
