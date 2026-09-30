# KI-21 Phase 1 — Hybrid Placement and Migration Design (Review Draft)

- **Status:** Proposed hybrid placement; local no-user-data Worker prototype implemented; Gitea control-plane transition planned by Wasabi; user-reported Gitea 1.27.1 requires upgrade and strict migration-egress verification before import; not architecture approval or Cloudflare deployment authorization
- **Evidence date:** 2026-09-30
- **Baseline:** [`Phase 0 capability and data baseline`](phase0-capability-baseline.md), source revision `18ae8cf`
- **Scope:** Recommend where each capability should run and define compatibility, security, data, cost, and rollback gates. A local synthetic Worker prototype was added; no Cloudflare account resource, service, secret, route, database, retained volume, CI job, or deployment was changed.
- **Cloudflare documentation checked:** 2026-09-27; account inventory is reconnaissance only, not proof that existing resources are reusable or that a product/plan is enabled.

## 1. Recommendation

Adopt a **hybrid boundary, not a wholesale migration**:

1. Use Cloudflare for edge DNS/proxy/security and, once the Kokonut App frontend exists, static delivery through Workers Static Assets (or a framework-specific Worker runtime if the app requires SSR).
2. Keep the governed backend and stateful/compatibility-sensitive services on Coolify initially: PostgreSQL/PostGIS, Directus and extensions, FastAPI Gateway, and any measured ClickHouse, Redis, MQTT, gRPC, or durable worker dependencies.
3. Treat a thin Worker API/BFF and Hyperdrive as a later, isolated pilot—not a replacement for Directus, the Gateway, or the canonical database. A private PostgreSQL path requires the currently documented Beta Workers VPC Service and a Cloudflare Tunnel in the database network, TLS, new scoped DB credentials, and real PostGIS/transaction/security tests; VPC service creation also requires Connectivity Directory Admin.
4. Consider R2 only for a **new, permission-tested upload path** after Directus storage compatibility and recovery are demonstrated. Do not migrate the retained Directus upload volume in this phase.
5. Wasabi has decided to migrate Kokonut source control and project tracking from OneDev to the existing Gitea organization. OneDev remains the source of truth until Wasabi completes the migration and verifies the imported repository/tracking data. Then use Gitea as the control plane; validate/recreate its CI runner, workflows, secrets, branch protections, and approvals separately. Do not treat those as part of repository-item migration or trigger a Staging deployment.
6. Keep Metabase outside the default Backend Brain target. Preserve its present configuration/data until an explicit archive/removal decision is made.

This uses Cloudflare's edge and serverless capabilities without moving canonical data, bypassing the existing governed API, or creating a second source of truth. The future Kokonut App remains the presentation layer over modular, farm- and chain-agnostic backend capabilities.

## 2. Service-fit matrix

| Capability | Recommended placement now | Cloudflare candidate | Decision and required proof |
|---|---|---|---|
| DNS, proxy, public edge security | Cloudflare zone/proxy in front of the approved origin path; origin remains on Coolify | DNS, WAF/rules, rate controls, caching only for explicitly safe assets/responses; Tunnel for private origin ingress | Keep public API caching disabled by default. Revalidate Caddy routes, origin reachability, host exposure, auth passthrough, request-size/time limits, and rollback before changing a hostname or rule. Existing Tunnel configuration is not changed here. |
| Future Kokonut App frontend | Not yet deployed; choose its framework and API contract first | Workers Static Assets for an SPA/static build; framework-specific Worker runtime only if SSR is required | Good first compute candidate once an actual frontend exists. No current frontend implementation is being migrated. Separate static assets from authenticated API/data and verify cache headers, CSP, CORS, preview isolation, and accessibility. |
| Thin BFF / edge routing | Existing FastAPI Gateway remains authoritative on Coolify | TypeScript Worker or a narrow Python Worker for selected, stateless HTTP composition | Optional pilot only. Avoid duplicating auth, tenant/location policy, lifecycle transitions, or audit. Start against a mock or isolated test API; every path must preserve error shape, request identity, scope, rate/abuse controls, and audit semantics. |
| Directus REST/GraphQL, admin, hooks/extensions | Coolify beside canonical PostgreSQL and required cache/storage | No direct port proposed | Preserve Directus roles, hooks, schema metadata, extension compatibility, and operational workflows. A Worker binding is not a binding available inside the existing Directus container. Evaluate storage adaptation independently. |
| FastAPI Gateway and Python APIs | Coolify; keep current API contract and container/runtime | A separate Python Worker pilot is technically possible for a small compatible surface | Do not port the Gateway wholesale. Cloudflare documents FastAPI support in Python Workers, but its Python Worker environment uses a separate runtime/package model (currently Python `>=3.13` with supported pure/PyEmscripten/Pyodide packages); the KI container baseline and its native/database dependencies require an import, lifespan, driver, and route-by-route compatibility audit. |
| Linux-only/stateless compatibility workload | Coolify if an identified workload still needs a full Linux image | Cloudflare Container behind a Worker, only for a specific bounded stateless HTTP workload | Not a generic Compose host: the Worker handles inbound HTTP; Containers start on demand, may have a slow first request, stop when idle, and have temporary local disk. Verify instance sizing, scale behavior, outbound access, logs, and workload tolerance before a synthetic-data pilot. No current KI workload is selected for this placement. |
| PostgreSQL/PostGIS canonical store | Coolify; remains source of truth | Hyperdrive + Workers VPC only for a later Worker pilot | Hyperdrive is a Worker binding, not a generic database proxy for KI containers. Workers VPC is currently documented as Beta and needs a VPC Service plus Cloudflare Tunnel, TLS, and Connectivity Directory Admin to create. Require a least-privilege pilot role, PostGIS extension/query tests, transaction/prepared-statement tests, and explicit cache/read-after-write policy. Hyperdrive pools in transaction mode, so session state must not be assumed across transactions; caching does not invalidate on writes. Begin read-only; do not expose DB publicly or move it to D1. |
| ClickHouse analytics/outbox | Coolify while real consumers and volume are measured | No replacement selected | Keep if ingestion/outbox or analytics workloads justify it. Inventory actual queries, retention, data volume, replay and restore before reconsidering; D1/KV are not drop-in analytical replacements. |
| Redis | Coolify if active Directus and other required consumers remain | No replacement selected | Distinguish Directus cache/rate-limit settings from the Gateway's process-local limiter. Verify each client and rebuild/invalidation semantics before removing or moving Redis. |
| MQTT sensor broker / subscribers | Coolify or explicitly managed worker host | No Workers replacement selected | MQTT/TLS certificates, ACLs, persistent broker queues and subscriber semantics are protocol/state dependencies. Preserve until actual devices, retries, queue disposition, and recovery are tested. |
| gRPC API | Coolify behind the tested Caddy/proxy path | No Worker/Container migration selected | Validate HTTP/2/h2c, TLS, long-lived connection behavior, API-key scope and reconnects with real SDK clients. Do not infer compatibility from ordinary HTTP proxying. |
| Scheduler, event bus, Prefect and CLI jobs | Explicit Coolify worker/cron ownership; PostgreSQL remains durable state | Worker Cron/Queues only for a future refactor with measured semantics | Keep one active dispatcher per recurring task. Any refactor must preserve leases, retries, idempotency, dead-letter controls and operator replay; do not make edge triggers a second scheduler. |
| File/media bytes | Retain current volume and authorization path until inventory/backup gates clear | R2 as an opt-in target for new uploads or a synthetic-data pilot | R2 supports S3-compatible presigned GET/HEAD/PUT/DELETE operations; presigned POST form uploads are not supported, and presigned URLs use the S3 API domain rather than a custom domain. A presigned URL is a bearer credential. Validate whether the mobile client can use PUT, object-key tenancy, short expiry, content type, CORS, upload completion, malware/size checks, metadata linkage, authorized reads/deletes, checksums, export and restore before any real data is moved. |
| Metabase and dashboard assets | Exclude standalone Metabase from the default target; preserve existing data/assets pending disposition | Kokonut App BI over governed APIs/datasets; Metabase only as a separately justified opt-in | No Production dashboard users are known to rely on it. This is not authorization to remove the current Compose service, DB, volume, or dashboard files. |
| CI/CD and release approvals | OneDev is the interim source/control plane until Wasabi completes the Gitea migration; Gitea is the intended target | Evaluate Gitea Actions with an approved runner for Wrangler after migration and workflow-parity checks | Do not assume OneDev build history, jobs, secrets, webhooks, branch protections, required checks, or approvals migrate with issues/PRs. Recreate and verify them separately; preserve paused Staging auto-deployment and manual Production approval; use one deployment authority and do not add a duplicate trigger. Cloudflare Workers Builds is not required. |
| Logs, metrics, and incident response | Existing Coolify/VPS observability plus KI health/logging, pending owner/SLO definition | Workers/Containers observability for any adopted edge workload | Define retention, alert destination, request correlation, incident owner and cost before relying on platform logs as the system of record. Test diagnosis when either Cloudflare or the origin is unavailable. |

## 3. Proposed request and data boundaries

```text
Browser / Field Collector
  ├─ public static Kokonut App assets ──> Cloudflare Workers Static Assets (future)
  └─ governed API calls ──> Cloudflare edge controls ──> approved origin path
                                                    └─> Caddy / FastAPI Gateway / Directus on Coolify
                                                         └─> PostgreSQL + PostGIS (canonical)
                                                              └─> ClickHouse projection/outbox (if required)

Optional, separately approved Worker pilot:
  Worker ──> Hyperdrive ──> Workers VPC Service ──> cloudflared Tunnel ──> private PostgreSQL
```

The API origin path (including whether a route goes directly to the current Gateway or through a Worker BFF) remains a decision for the pilot. Avoid a Cloudflare Worker route that loops back through the same public hostname. No direct public database port, new VPC/Tunnel, new Worker, or R2 bucket is authorized by this design draft.

## 4. Ordered Phase 1 work and gates

### 1A — Close baseline safety inputs (read-only until separately approved)

- Assign named human owners for canonical data, operations, secrets, backups/restore, and independent approval; the repository does not assign this RACI.
- Inventory the eight retained Staging volumes, record size/contents classification and seed-versus-historical/manual/user-originated data, then agree archive and disposition. **Do not prune or delete volumes.**
- Resolve the authorized test-secret injection path. Prior local test attempts hit the documented SOPS fail-closed path; no identity/key diagnosis or secrets change was performed.
- Keep the OneDev Staging trigger paused throughout the control-plane transition. Reconcile current trigger/job behavior read-only and verify that Gitea does not introduce a duplicate deployment trigger; Staging remains paused unless Wasabi separately approves reactivation.
- Reconcile backup policy with actual scripts, including Directus media, Metabase metadata if retained, Mosquitto state if valuable, decryption, and an isolated restore rehearsal.

### 1B — User-led OneDev-to-Gitea migration (planned; not executed by this agent)

- **Decision (2026-09-30):** Wasabi will migrate the Kokonut repository and tracking workspace from OneDev into the Gitea organization already created. Wasabi will run the migration flow after this plan is ready. The selected migration items are **Milestones, Labels, Issues, and Pull Requests**. This supersedes earlier plan text that treated OneDev as the long-term control plane and Gitea only as an emergency contingency.
- **Current target reported by Wasabi (2026-09-30): Gitea 1.27.1.** Do not run the built-in import from that version: it is within the affected range for the OneDev migration denial-of-service advisory (through 1.27.2), predates the 1.27.3 private-attachment fix, and is specifically where the redirect-SSRF correction was reverted.
- **Updated release path (2026-09-30):** Gitea 28.0.0 (the new versioning drops the historical `1.` prefix from 1.28.0) was released today and is listed as patched for the redirect-SSRF advisory. Its release routes migrations/mirrors/Git network operations through an internal proxy with configurable egress. The migration flow is functionally supported; this is a security gate, not a compatibility claim that the import cannot work. Upgrade from Wasabi-reported 1.27.1 only after reviewing the release breaking changes, verifying backups, Git >=2.25, `ROOT_URL`, and migration egress settings.
- Before the one-time import, configure and verify `[migrations] EGRESS_MODE = strict` and `ALLOWED_HOST_LIST` limited to the trusted OneDev source host/required port; confirm redirects to loopback/private/internal hosts are denied. The release defaults egress mode to `lax`, so do not rely on defaults. In strict mode, host entries without ports permit only 80/443. Review `BLOCKED_HOST_LIST` and the new egress policy, limit migration permission to trusted operators, test private attachments with authorized and unauthorized viewers, and disable/restrict migration capability after import.
- **No-mirror clarification:** Wasabi will use a one-time import, not a pull mirror. This avoids scheduled repeated fetch exposure, but the advisory also demonstrates a one-time migration attack using the initial clone, so no-mirror alone does not remove the redirect-SSRF risk. Keep mirror mode disabled and use the v28.0.0 strict-egress gate.
- **Checkpoint done (2026-09-30):** validated KI plan/prototype content is committed as `d78efe9` on `chore/ki-21-phase-0-baseline` and pushed to the OneDev `origin` remote for migration. The unrelated `uv.lock` Python-version edit remains local and uncommitted; it is excluded unless separately reviewed and approved.
- In the migration flow, include the selected tracking items and preserve Git history, branches, tags, and LFS objects if present. Use one-time import mode, not pull-mirror mode. Verify what the actual instance/version imports rather than assuming every issue/PR field is preserved.
- After import, compare repository refs and item counts; inspect representative open/closed issues and PRs, labels, milestones, associations, comments, attachments, review state, cross-references, and PR head/base branches. Confirm organization/team access and default branch. Keep OneDev available as a rollback/source reference until this audit passes.
- CI/control-plane cutover is a separate gate: reconcile Gitea Actions workflows and runner labels, secrets, webhooks, required checks, branch protections, and human approvals. These are not among the selected migration items and must not be assumed to transfer. Keep Staging auto-deployment paused and Production promotion manual; ensure only one CI system can deploy after cutover.
- Once Wasabi confirms the import, update issue references and finalize this plan in Gitea. No OneDev repository migration, CI cutover, Gitea write, Staging change, Cloudflare resource change, or deployment is performed by this agent.

### 1C — Local proof completed; remote preview remains gated

- Implemented a local-only synthetic Worker + Static Assets proof in [`prototypes/cloudflare-edge-preview`](../prototypes/cloudflare-edge-preview/README.md): static preview, `/healthz`, explicit unavailable `/api/*`, restrictive static-asset headers, and no KI backend/data bindings.
- Verification on 2026-09-29: `npm run validate` passed Wrangler type generation, TypeScript checking, classic-script syntax checking, **4 Vitest runtime tests**, and `wrangler deploy --dry-run`. A local Wrangler session served the page and verified `/healthz` = 200, `/api/farms` = 404, `POST /healthz` = 405, and unknown asset = 404; the browser rendered the healthy-but-disconnected status.
- These checks establish local behavior only—not a Cloudflare account deployment, public URL, Gitea Actions integration, external access control, or remote runtime parity.
- A remote non-production Worker preview still requires separate resource/deployment approval with the target account/name, public-preview access controls, and an agreed usage/cost boundary. If approved after Gitea cutover, test Gitea Actions/runner `wrangler` build/deploy, environment isolation, scoped token handling, logs, rollback/version restoration, and deletion procedure; leave public production DNS and current Staging routes unchanged.
- Do not connect the first remote preview to live PostgreSQL, Directus, R2 user data, production secrets, or legacy volumes.

### 1D — Evaluate backend offload only if the local/remote preview demonstrates value

- First compare an edge Worker calling the existing, policy-enforcing Gateway with a direct database pilot. Prefer the existing API contract unless measured latency/cost or product needs justify a new database path.
- For Hyperdrive/VPC, use a disposable database clone or approved isolated staging target, TLS, a dedicated read-only DB role, and representative PostGIS reads. Test connection/pool limits, transaction behavior, cache staleness/read-after-write, location isolation, timeouts, and origin outage behavior.
- Expand to writes only after human-governed lifecycle, audit, idempotency and rollback tests prove parity. Do not route production writes through the pilot.

### 1E — Evaluate media independently

- Only if new upload requirements justify it, test R2 with synthetic objects and the actual Field Collector/Directus authorization model.
- Compare upload/download/delete, expiry and replay of signed URLs, browser CORS, object/metadata consistency, interrupted mobile sync, checksums and full export/restore.
- Existing volume migration requires an inventory, verified backup, owner-approved mapping and a separately approved cutover/rollback plan.

## 5. Cost, security and acceptance criteria

- No TCO estimate is asserted: request volume, egress, Worker execution, object count/size, retention, Tunnel topology and current Cloudflare plan eligibility are not established by Phase 0. Current Workers documentation says requests served directly as static assets are free/unlimited and static asset storage has no additional charge, while requests that invoke Worker code are billed under Workers pricing; other product, storage, security and network costs still need a measured estimate. Build a monthly comparison against Coolify compute, storage, backup, bandwidth and operator effort before approving paid resources.
- Keep API and personalized responses non-cacheable unless a route has explicit public-data eligibility, short freshness, invalidation and privacy tests. Never cache credentials, device sync state, private farm data, or admin routes.
- Keep secrets in the active CI/Cloudflare secret stores with distinct per-environment scope; recreate and verify CI secrets during Gitea cutover rather than assuming OneDev secrets transfer. No secrets in source, build logs, frontend assets, or uploaded Worker bundles.
- Preserve role/location authorization at the canonical backend. A signed file URL is a bearer token and does not itself enforce farm membership after issuance.
- Require test evidence for functional parity, authorization denial cases, tenant isolation, audit durability, API contracts, load/concurrency, timeout/retry behavior, observability, data backup/restore, cost, and rollback before each capability moves.
- A successful Worker deployment, database ping, or file upload is only a component test—not a migration acceptance result.

## 6. Decisions still open

1. Which named human owners approve data disposition, security, backup/restore, and Production release?
2. Which retained Staging volumes contain unique or user-originated data, and what is their approved disposition?
3. Which Kokonut App frontend framework and user workflows are actually prioritized? There is no frontend implementation to migrate yet.
4. Which API reads, if any, benefit from an edge BFF or direct Hyperdrive path enough to justify a duplicate runtime/auth boundary?
5. Are new mobile/photo uploads a near-term requirement, and what retention/privacy rules apply?
6. Which Cloudflare products/features and plan are eligible, and what usage budget/SLO should the proof meet?
7. Which operational log/alert destination and incident owner cover Cloudflare-to-Coolify failures?
8. After import, which Gitea Actions workflows, runner labels, repository secrets, branch protections, and required checks are approved for the canonical CI path?

## 7. References

Cloudflare references checked 2026-09-27; Gitea references checked 2026-09-30.

- [Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/) — static assets and Worker code can be deployed/routed together; [billing and limits](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/) — static asset versus Worker-script charges.
- [Python Workers packages and FastAPI](https://developers.cloudflare.com/workers/languages/python/packages/fastapi/) and [package compatibility](https://developers.cloudflare.com/workers/languages/python/packages/) — Python Worker runtime/dependency constraints.
- [Hyperdrive: how it works](https://developers.cloudflare.com/hyperdrive/concepts/how-hyperdrive-works/) — origin connection pooling, query caching and read-after-write considerations.
- [Workers VPC private-database connection](https://developers.cloudflare.com/hyperdrive/configuration/connect-to-private-database-vpc/) — Tunnel, TLS and VPC Service requirements.
- [R2 presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/) — supported operations, CORS and bearer-token cautions.
- [Containers fundamentals](https://developers.cloudflare.com/containers/concepts/) and [limits/instance types](https://developers.cloudflare.com/containers/platform/limits/) — request routing, on-demand lifecycle, resource sizes and ephemeral local storage.
- [Workers Builds Git integrations](https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/) and [external CI/CD](https://developers.cloudflare.com/workers/ci-cd/external-cicd/) — supported providers and deployment from other CI systems.
- [Gitea migration API](https://docs.gitea.com/api/operations/repo-migrate/) — accepts `onedev` as a migration source and exposes milestones, labels, issues, pull requests, LFS, releases, and wiki options.
- [Gitea 28.0.0 release notes](https://blog.gitea.com/release-of-28.0.0/) — released 2026-09-30; documents the internal Git proxy, migration egress settings/defaults, Git version floor, and breaking changes.
- [Official Gitea releases](https://github.com/go-gitea/gitea/releases) — verify the deployed release and its security fixes before import.
- [Gitea OneDev migration security advisory GHSA-46px-6cqx-c5fv (CVE-2026-60018)](https://github.com/go-gitea/gitea/security/advisories/GHSA-46px-6cqx-c5fv) — affected versions through 1.27.2; patched in 1.27.3.
- [Gitea migration redirect/SSRF advisory GHSA-82f7-87hm-852x](https://github.com/go-gitea/gitea/security/advisories/GHSA-82f7-87hm-852x) — the 1.27.1 reversion and proxy/egress mitigations for Git HTTP redirects.
- [Gitea private-attachment authorization advisory GHSA-frpv-2xgv-wxpq (CVE-2026-78433)](https://github.com/go-gitea/gitea/security/advisories/GHSA-frpv-2xgv-wxpq) — some pre-2026-01-16 private attachments could be served through public-repository paths; patched in 1.27.3.
