# Kokonut Intelligence front ends

This npm workspace is the implementation foundation for the three applications
described in [`docs/refactor/frontend-modernization.md`](../../docs/refactor/frontend-modernization.md).
The current React screens are partial migrations. General Operations includes
read-only report review and metric listing; other workflows link to the current
Gateway interfaces. These slices do not claim full feature parity or change
server authorization.

`@kokonut/operator-client` centralizes same-origin, no-store requests to the
operator Gateway API, operator CSRF handling, normalized HTTP errors, and
cancelable latest-request tracking. It intentionally does not handle the
Delphi participant invite/session or Field Collector device-token protocols.
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
