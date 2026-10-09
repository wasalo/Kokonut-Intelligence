# KI Cloudflare edge preview

A local-only proof of the first hybrid-design slice: serve a synthetic static page from Workers Static Assets and use one small Worker route for a health check.

## Safety boundary

- `workers_dev` is disabled; no route, custom domain, or account ID is configured.
- There is no KI API, Directus, PostgreSQL/PostGIS, Hyperdrive, R2, authentication, secret, or real farm data binding.
- `/api` and `/api/*` are explicitly unavailable; they never proxy to another service.
- All page content is synthetic and served from `public/`.
- This project has no deployment script. Do not add a route, enable `workers_dev`, or deploy it without separate review and approval.

## Run locally

From this directory:

```sh
npm ci
npm run validate
npm run dev
```

Then open the local URL printed by Wrangler. The page calls only `/healthz` on the same local Worker. Use `Ctrl-C` to stop the server.

`npm run validate` regenerates Worker binding types, type-checks the Worker and tests, checks the classic client script syntax, runs the Cloudflare Vitest runtime tests, and packages a Wrangler dry run. It does not deploy or contact KI services. Node.js compatibility is explicitly disabled because this prototype uses no Node.js built-ins; enable it only after dependency/runtime review.

## Routes

- `GET /` — static preview page.
- `GET|HEAD /healthz` — no-store health response identifying synthetic-only mode.
- Other methods on `/healthz` — `405` with `Allow: GET, HEAD`.
- `/api` and `/api/*` — JSON `404`; no backend is connected.

## Scope / follow-up

This validates the local Worker + static-assets shape only. It is not an account deployment, public preview URL, DNS change, Staging cutover, or proof of production parity. A later remote preview must first confirm its account, resource name, access control, and cost/usage boundary.
