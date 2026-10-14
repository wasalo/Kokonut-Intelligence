# Open Follow Ups

Updated: 14 October 2026. This file collects decisions, access, fixtures, and
physical resources that the refactor cannot safely infer. Local implementation,
offline tests, disposable-database acceptance, and documentation continue while
these items are open.

Do not put passwords, API tokens, client secrets, private keys, or vault
passphrases in this document. For credentialed items, provide the provider and
non-secret configuration, then provision credentials through the encrypted
secret workflow.

## Decisions and source data

| ID | Needed from the repository owner or capability owner | Why it blocks closure |
| --- | --- | --- |
| OFU-01 | For each non-demo location in populated deployments: location name/ID, exclusive tenant owner organization, any explicitly shared organizations, and the accountable confirmer. The confirmed exclusive owner for seeded Kokonut Adelphi and Kokonut Genesis is Kokonut Network. | Migration/backfill and row-level security must not infer ownership from an arbitrary organization relationship. Unknown locations and unlocated records stay unassigned. |
| OFU-02 | For each legacy OIDC operator: organization membership and allowed location/resource/action scopes; identify disabled or departed operators. | Existing NULL-tenant grants cannot be converted safely without the human-to-organization mapping. |
| OFU-03 | Product/jurisdiction retention periods for notifications, attempts, operator audit, mobile collections, media, canonical derivatives, exports, and backups; legal-hold rules; who may approve retain/archive/erase; treatment of already withdrawn or retired-form records. | The interim policy is fail-closed and does not prune protected rows. Human disposition and lawful periods cannot be inferred from code. |
| OFU-04 | Name accountable owners for retained reports/dashboards and select each retained surface, audience, tenant/location scope, measures, filters, and a reference export/fixture. | The archived metadata includes generic demo cards and unlocated reports. Source registration is not proof of ownership or expected output. |
| OFU-05 | Select the production external alert destination and accountable on-call owner (SMTP, webhook, or other supported adapter), plus routing/severity expectations. | Local outbox and adapter code do not prove delivery, alert response, or operational ownership. |
| OFU-06 | Confirm the production scale/deployment target and availability expectations: replica count, failover/RPO/RTO, public ingress and trusted proxy hops, and who approves the cutover/legacy-service retirement. | Local loopback profiles and private-network checks do not establish production topology or authorize cutover. |

## Provider and environment access

| ID | Needed | Safe handling / current state |
| --- | --- | --- |
| OFU-07 | Production OIDC issuer URL, application/client ID, redirect/logout URLs, authorized test identities, and operator provisioning owner. | Keep the client secret in encrypted `.env.sops`; never paste it here. Source adapters and profile checks exist; a real provider and browser login are not configured. |
| OFU-08 | Cloudflare R2 account/bucket/endpoint, dedicated least-privilege credentials, retention/lifecycle policy, and a test prefix or non-production bucket. | Provision credentials only through encrypted secrets. The production R2 backup and live object inventory/delete acceptance are not configured. |
| OFU-09 | Directus test/runtime identity and a disposable database/schema matching the supported Directus version, including representative roles/fields/rows and hooks. | Do not point parity checks at production. The current archived Directus snapshot has a documented schema mismatch; runtime-role parity remains open. |
| OFU-10 | Local browser unlock of the Field Collector vault and the candidate browser session when available. | An isolated Chrome context has now verified `navigator.onLine=false`, cached-shell reopen, encrypted local capture, and reconnect retry against mocked API responses ([evidence](builds/2026-10-14-recovery/field-collector-browser-offline-client.json)). Unlock the existing vault only in the browser; do not send the passphrase. Live candidate API re-enrollment and retired-form consent flows remain open. |
| OFU-11 | Trust the candidate's local development HTTPS CA in the browser/OS, or provide an existing approved local certificate. | The earlier browser refused the untrusted certificate. We will not bypass the browser warning. HTTP loopback checks are passing. |

## Physical and timed acceptance

| ID | Needed | Why it blocks closure |
| --- | --- | --- |
| OFU-12 | A Raspberry Pi/ARM64 target with at least 4 GB RAM, SSD, power supply, and network access, or an agreed hardware test owner and window. | CI builds ARM64 images, but the required real-device bootstrap, restore, thermal/resource, and restart acceptance has not run. |
| OFU-13 | A controlled 24-hour availability window and resource budget for the recovery/concurrency run; identify whether the candidate may be unavailable during the run. | Short restart/retry checks are not evidence for a 24-hour recovery/scale gate. |
| OFU-14 | A populated, sanitized reference dataset/exports for each selected report and downstream consumer, with data owner and allowed use. | Synthetic fixtures cover contracts but cannot close semantic parity on real populated outputs. |

## Additional product and provider decisions

| ID | Needed | Why it blocks closure |
| --- | --- | --- |
| OFU-15 | Confirm whether any production integration still requires Directus API, admin UI, or hooks; if so, name the retained consumers and the intended user-to-location grant model. | The archived Field Worker rule uses `$CURRENT_USER.location_id`, but the archived `directus_users` table has no `location_id`; a disposable runtime probe failed closed for both synthetic own-location and other-location reads. Do not infer a replacement access model or retirement scope without the supported-consumer decision. See [Directus parity inventory](directus-parity-inventory.md). |
| OFU-16 | Identify the authoritative production schedule/provider configuration (PostgreSQL scheduler, Prefect, host cron/systemd, GitHub schedules, or other), the active job inventory, and accountable operators; provide a read-only export or approved access. | The candidate reports no scheduled jobs and has no Prefect service, but host/external scheduler state was not queried. The source inventory alone cannot prove which production schedules are active or who owns their recovery. See [schedule ownership inventory](schedule-ownership-inventory.md). |

## Answers

When ready, reply with the ID and answer, or edit this file directly. Names and
IDs are enough for ownership mapping; do not provide secret values here. Any item
that remains undecided stays fail-closed and is not treated as accepted.

## Additional candidate operation

| ID | Needed from owner | Why it blocks closure |
| --- | --- | --- |
| OFU-17 | Approve or defer applying the remaining 30 curated reference seeds to the local candidate. | This writes reference data to the candidate. The exact list and rollback procedure are prepared in [candidate rollout preflight](builds/2026-10-14-recovery/candidate-curated-seed-rollout-preflight.json). A fresh age-encrypted checkpoint was restored into an isolated `template0` database with matching migration and extension fingerprints and selected row counts. The candidate remains unchanged. Recommended scope: apply only the 30 listed seeds, leave the other 90 sources pending, exclude `seed:064-068_impact_network.sql`, and do not rerun `seed:140_mobile_forms.sql`. If any selected seed fails after earlier transactions commit, restore the verified checkpoint. |
| OFU-18 | Separately approve or defer rolling migrations 392–395 to the local candidate. | Migrations 392–395 passed isolated PostgreSQL 16 replay and forced-RLS credential/context/session-role acceptance, but only migration 391 is applied on the candidate. The rollout requires a fresh encrypted checkpoint and restore rehearsal, ordered migration application, candidate-app-only rebuild/recreation, and post-rollout health, migration, and protected-route checks. It does not authorize RLS; keep RLS disabled. The candidate has not been changed by migrations 392–395. |

The owner’s 14 October instruction authorizes test execution and directs
unanswered decisions into this document. Candidate seed SQL has not run and
migrations 392–395 have not been rolled out; these candidate writes remain separately
gated under OFU-17 and OFU-18.
