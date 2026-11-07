# Kokonut Intelligence front ends

This npm workspace is the implementation foundation for the three applications
described in [`docs/refactor/frontend-modernization.md`](../../docs/refactor/frontend-modernization.md).
The current React screens are partial migrations. General Operations includes
read-only submitted-report review, metric listing, and the location-scoped
coordination overview. Field Operations includes a read-only farm activity
summary. Governance includes a read-only facilitator recommendation queue.
Other workflows link to the current Gateway interfaces.
These slices do not claim full feature parity or change server authorization.

`@kokonut/operator-client` centralizes same-origin, no-store requests to the
operator Gateway API, operator CSRF handling, normalized HTTP errors, and
cancelable latest-request tracking. Each vertical shell provides one shared
operator-session lookup for all of its routes and exposes the Gateway-backed
sign-in/sign-out actions. The Gateway returns the CSRF token only from the
authenticated, no-store session response after matching it to the server-side
session hash; the cookie remains scoped to `/operator`. Sign-in returns the
operator to the app path where they started. The client intentionally does not
handle the Delphi participant invite/session or Field Collector device-token
protocols.
Mutation retries remain the caller's responsibility and must reuse the
original request ID and unchanged payload.

## Local development

Run commands from this directory with Node.js 22.22 or newer:

```sh
npm ci
npm run dev:ops
npm run dev:field
npm run dev:governance
```

Each development server uses its production path prefix: `/ops/`, `/field/`, or
`/governance/`. Gateway and preserved legacy paths proxy to
`http://127.0.0.1:8000` by default; set `KOKONUT_GATEWAY_DEV_TARGET` to override
that target. Build apps independently with `npm run build:ops`,
`npm run build:field`, and `npm run build:governance`.

This proxy makes local routing convenient. It does not substitute for the
trusted HTTPS and browser identity acceptance in G4.

The Wrangler configurations keep automatic public deployment disabled until
the candidate origin, route ownership, and Cloudflare deployment environment
are reviewed. Do not deploy these shells as a production replacement for the
current operator, Delphi participant, or Field Collector interfaces.

## Production path ownership

Each Worker claims only its app prefix: `/ops` and `/ops/*`, `/field` and
`/field/*`, or `/governance` and `/governance/*`. Keep the Gateway and retained
interfaces on the VPS origin at `hub.kokonut.network`: `/operator/*`,
`/api/mobile/*`, and `/participation/*` must continue through Cloudflare to
Coolify's Gateway route. The front ends make same-origin requests, preserving
the Gateway's operator session and CSRF behavior. The `hub.kokonut.network`
DNS record must be Cloudflare-proxied for its
[Worker routes](https://developers.cloudflare.com/workers/configuration/routing/routes/)
to run. Keep Coolify configured as the origin for requests outside the three
app prefixes.
Do not attach a hostname-wide Worker route unless that Worker explicitly
forwards the retained Gateway paths to the origin.

After G4 approves the trusted origin and Cloudflare credentials are provisioned,
deploy an individual static app from this directory with `npm run deploy:ops`,
`npm run deploy:field`, or `npm run deploy:governance`. Each command builds only
that app and deploys it to the route in its Wrangler config. These commands do
not create DNS records or configure ZITADEL, R2, or the Coolify Gateway origin.
Keep Cloudflare credentials in the operator's environment or secret store; do
not add them to this workspace.
