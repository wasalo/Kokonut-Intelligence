# Kokonut Intelligence refactor closure checklist

This checklist groups the remaining work needed to accept the candidate refactor, from exact-head CI through final owner sign-off. It is an action tracker, not a second acceptance register: the [candidate completion guide](current-state-and-implementation.md) remains authoritative for gate status, decisions, and evidence. Update that guide whenever a check is completed or its result changes.

The target is **candidate acceptance**. Passing this checklist does not by itself approve production cutover, legacy retirement, physical edge-device support, or the deferred Scale profile.

## Completion rules

- Evaluate code and CI against the exact branch head being deployed. A prior green run does not validate later commits.
- Distinguish source checks, disposable tests, candidate behavior, and production behavior. Record which environment produced each result.
- Keep database grants unchanged unless caller evidence and a separately reviewed migration justify a change. The Standard API and general worker currently share the kokonut_runtime database login; do not claim separate API and worker identities.
- Verify secret isolation through allowlisted key presence and service boundaries. Never print or copy secret values into logs or evidence.
- Use only owner-provided operational data and boundaries. Keep personal or participant data out of fixtures; use synthetic participant records for consent tests.
- Before candidate migrations or recovery drills, follow the checkpoint and restore procedure in the canonical guide. Preserve candidate database volumes.
- A checked item needs a linked result, evidence artifact, or owner decision. A page loading, successful deployment, synthetic storage probe, or source review alone does not close a runtime or parity gate.
- If a prerequisite is blocked, record the exact missing input and keep dependent items open.

## Ordered checklist

### G1 — Exact-head build and CI

The previous remote head `d61d0b308be7a0257e7a9e9646aeaebcca197c85` passed all required CI jobs and Security. The Coolify validator then exposed a bind-path issue before Compose loaded. A relative-path and injected-environment fix is prepared in the worktree; after it is pushed, rerun both workflows on the new exact head before deployment.

- [ ] Confirm the required CI aggregate, integration suite, source checks, and AMD64/ARM64 image validation pass on the current PR head.
- [ ] Confirm the Security workflow passes on that same commit.
- [ ] If any job fails, capture its concise failure summary, fix the cause, run the focused check, then rerun CI and Security against the new exact head.
- [ ] Confirm PR #73 still targets develop and has an independent review before merging under the repository workflow.

**Acceptance evidence:** exact commit SHA, CI and Security run links, all required job conclusions, and any repair commit.

### G2 — Candidate rollout and database security

The source caller map has been confirmed and grants remain unchanged. Candidate acceptance is open until the current source is deployed and its runtime boundaries are verified.

- [ ] After G1 passes, take and verify the approved encrypted candidate checkpoint. Record the candidate target and current migration ledger without reading operational row contents.
- [x] Before the d61d0b30 deployment attempt, commit and read back a fresh signed, encrypted checkpoint for both PostgreSQL databases; the read-only ledger had 746 applied schema migrations through schema 755. The deployment failed before Compose loaded, so no migration or database change followed. Evidence: [checkpoint](builds/2026-11-15-recovery/g2-candidate-pre-deploy-checkpoint-2222z.json).
- [ ] Repeat the checkpoint immediately before the next deployment, then deploy the exact tested head to the selected Coolify candidate. Confirm Compose validation succeeds, the deployed image/source revision matches that SHA, and ordered migrations have zero pending work. The d61d0b30 attempt was rejected before Compose loaded because Coolify forbids `${...}` in bind-mount sources; see [deployment failure evidence](builds/2026-11-15-recovery/g2-coolify-bind-path-failure-2232z.json).
- [ ] Verify candidate health and identity discovery: Gateway readiness, ZITADEL discovery/issuer, and service health for the enabled profile.
- [ ] Using read-only checks, record that current Standard source runs the API and general worker as kokonut_runtime; do not report them as separate identities. Confirm isolated children use their dedicated configured logins and cannot fall back to kokonut_runtime. The desired API/worker split is a C1 follow-up and stays open until implemented and verified.
- [ ] Check service environment key presence against the source allowlist. Confirm raw runtime credentials appear only in services that need them; isolated children retain the shared-database deny marker and do not receive shared credentials. Record presence only, never values.
- [ ] Confirm database grants have not changed. Record source/image digests, migration status, identity results, health results, and secret-presence counts in sanitized evidence.
- [ ] Keep C1 open unless its reviewed caller cohorts and grant-narrowing evidence are separately complete; this deployment check alone does not close C1.

**Acceptance evidence:** exact source/image provenance, ordered migration status, read-only runtime identity checks, allowlisted secret-presence results, and no unexplained service or health failures.

### G3 — Candidate capability parity and MAN-CAP outcomes

Source outcomes and cross-cutting source reviews are accepted. Candidate behavior and final MAN-CAP outcomes remain open. Use the per-capability acceptance coverage and capability matrix in the canonical guide; do not replace their detailed expected behavior with a single aggregate pass.

- [ ] For every CAP row, identify its candidate route or explicitly record that no candidate path exists. For Directus-only compatibility slices, use the documented local Docker disposable checks; Directus is not part of the Standard VPS profile. For implemented candidate paths, link the fixture or populated reference, expected result/tolerance, actor scope, and evidence.
- [ ] Complete candidate acceptance by primary review group:
  - [ ] Farm / Collector
  - [ ] Governance / agents
  - [ ] Finance / credits
  - [ ] Reports / providers
  - [ ] Administration
- [ ] For each applicable path, check authorized and denied scopes, location/tenant isolation, privacy redaction, lifecycle and human-review boundaries, audit attribution, and retry/idempotency behavior.
- [ ] Use frozen or owner-approved populated fixtures for output parity. Mark data-dependent rows blocked until G5 data and expected outputs exist; return to those rows after G5.
- [ ] Record a MAN-CAP disposition for every capability row: accepted candidate behavior, explicitly accepted limitation, or still open. Do not treat an accepted source outcome as a candidate outcome.

**Acceptance evidence:** a disposition and linked candidate evidence for every CAP row, plus Wasabi’s recorded MAN-CAP decisions.

### G4 — Identity, relational workflows, and Field Collector

OIDC negative callbacks and the distinct farm-activity submit, verify, publish, reject, and rework paths have already been exercised. The remaining live work is location-boundary denial, relation writes, and a real-device Collector workflow.

- [ ] Enter Los Saladillos through the candidate administration flow using owner-provided coordinates and boundary data. Confirm its location and farm are linked to the intended tenant; do not invent boundary geometry.
- [ ] With an account granted only Adelphi access, request Los Saladillos data and attempt a location-scoped operation. Confirm denial (403/404), no protected data, and no write or audit side effect.
- [ ] Exercise relational writes with an owner-approved farm-entry workflow: link the new farm to the existing location, then link a plot, crop cycle, farm task, and farm activity where the chosen flow supports them. Confirm every relation resolves to the same location and correct parent; verify inconsistent cross-location references fail closed.
- [ ] On a dedicated real mobile device/profile, enroll the Field Collector with a bounded location scope. Record app/browser version and enrollment evidence without retaining credentials.
- [ ] Complete an offline capture using a controlled test form and synthetic participant data. Close/reopen the app while offline, then reconnect and confirm one durable server submission with no duplicate on retry.
- [ ] Exercise the application-encrypted media path on that device: capture a synthetic image, queue it offline, sync it, verify authorized retrieval/decryption and denied unauthorized access, then verify approved cleanup.
- [ ] Exercise consent and withdrawal using a test form revision that explicitly requires consent. The five built-in revisions currently mark consent not required, so they cannot prove a positive consent path. Confirm no collection or media sync proceeds without required consent and that withdrawal is enforced.
- [ ] Exercise an expired/retired form revision, enrollment revocation, and a second sync attempt. Confirm the old revision is rejected or handled by its documented migration policy, revocation blocks new sync, and intake disposition remains a separate human decision.
- [ ] Record device-side and candidate-side evidence for enrollment, offline persistence, consent, media, sync deduplication, denial, and downstream disposition.

**Acceptance evidence:** second-location denial with no side effects, bounded relational-write evidence, and device-backed offline/media/consent/sync results.

### G5 — Populated data, reports, providers, alerts, and media

Adelphi exists, but the accepted candidate still lacks populated operational and report-reference data. Wasabi owns the integration and R2 operations. No farm or report parity claim is accepted from synthetic data or a one-shot provider probe.

#### Populate and reconcile data

- [ ] Wasabi supplies the operational/report data dump and identifies its source and intended use. Keep the raw source in an approved private location.
- [ ] Prepare a reviewable source-to-schema mapping before import. Normalize identifiers, coordinates/CRS, units, dates/time zones, parent-child relationships, duplicates, nulls, provenance, and privacy-sensitive fields. Preserve existing baselines and historical rows.
- [ ] Run a non-writing validation first. Report row counts, rejected/ambiguous records, referential-integrity results, and aggregate-only previews; do not expose private descriptions, participant details, or credentials.
- [ ] Obtain owner approval of the mapping and report audience/disclosure for each reference output.
- [ ] Take and verify the pre-import checkpoint, apply the approved import idempotently, and compare persisted aggregates and representative calculations against the approved source outputs.
- [ ] Re-run data-dependent G3 CAP checks and report exports against the populated reference, including measures, units, lifecycle filters, location scope, and audience restrictions.

#### Enable integrations deliberately

For each integration, record owner, intended use, disabled/test/live state, SOPS variable names, least-privilege access, safe cadence, rate limit, retry/deduplication policy, and acceptance evidence. Keep recurring jobs disabled until those fields and their candidate checks pass.

- [ ] Weather/OpenWeatherMap: verify location-scoped observation and forecast behavior against Adelphi data; verify retry and deduplication before enabling recurring work.
- [ ] Remote sensing: verify Copernicus candidate behavior and positive-data parity. Resolve Earth Engine project registration/API enablement and service-account access before enabling Earth Engine.
- [ ] World Bank: reconcile the existing global import with the approved report/farm use; confirm it is not represented as location-specific data.
- [ ] EAS/RPC/Gnosis/Baal: resolve candidate endpoint availability, chain identity, freshness, reorg/retry handling, and bounded read behavior for each enabled chain before starting schedules.
- [ ] Email alerts: verify event-driven outbox creation, routing, retry, delivery, and duplicate handling. The static SMTP receipt is not event-driven alert acceptance.
- [ ] Field Collector media R2: complete the device-backed consent/upload/sync checks above and confirm the Gateway-only reader boundary.
- [ ] Report-export R2: after candidate redeployment, verify the dedicated writer credential is confined to its one-shot worker, then run an authorized request, worker export, separately granted download, audience review, and disposition against populated report data.
- [ ] Backup R2: configure the approved candidate cadence and verify upload, readback/checksum, restore, and recovery evidence. A prior checkpoint transfer or database-only restore is not full application recovery.
- [ ] Keep optional integrations paused when their credentials, provider access, safe retry/cadence, or source parity have not passed review; the owner’s goal to enable all integrations does not mean bypassing their acceptance.
- [ ] Configure Better Stack P1 delivery using the owner-approved five-minute acknowledgment policy: Gerkery Soto as primary and Alejandro as backup. Confirm both accounts accept their invitations and enable phone/push notifications; create the incident webhook/escalation policy; run one acknowledged-page test and one no-ack test that escalates after five minutes. Keep the P1 gate open until both outcomes and independent monitoring are evidenced.
- [ ] Implement and verify the selected P1–P4 routing policy, including email routing for non-page alerts, severity deduplication/grouping, and a test of the relevant escalation paths. See the policy in the canonical guide.

**Acceptance evidence:** approved normalized data mapping, populated parity results, per-integration candidate evidence and operational settings, report disclosure approval, working backup/restore path, and acknowledged/no-ack P1 results.

### G6 — Full candidate recovery and 24-hour soak

Do not start the soak until G1–G5 candidate prerequisites are accepted.

- [ ] Recheck shared-host CPU, memory, disk, and service resource limits immediately before the drill. Preserve co-hosted services and candidate data.
- [ ] Rehearse full Coolify application recovery in an isolated Coolify-managed recovery target, including database and ZITADEL state, immutable application images, configuration/secrets restoration, proxy/routing, migrations, and core workflows.
- [ ] Name a soak operator and an independent reviewer. The person running the drill cannot be the independent evidence reviewer.
- [ ] Run the 24-hour monitored candidate soak with one-minute health probes and at least 99.5% success outside the planned drill.
- [ ] Use a verified checkpoint no older than 24 hours. Demonstrate RPO of at most 24 hours, PostgreSQL stop/restart recovery within 15 minutes, no acknowledged write lost, and no stranded active lease.
- [ ] Restore the checkpoint into a fresh isolated project; verify health and checksums within two hours. Record failure injection, downtime/data loss, probe results, timings, rollback location, and reviewer findings.

**Acceptance evidence:** complete timestamped soak log, checkpoint age and checksums, failure/restoration measurements, full recovery record, and independent review.

### G7 — Final refactor acceptance

- [ ] Reconcile the final candidate behavior, CAP dispositions, schema/migrations, source/image digests, secret boundaries, provider status, and G6 evidence against the canonical guide.
- [ ] Obtain the independent review required by PR #73 and all exact-head CI/Security checks. Merge through GitHub to develop only when repository protections pass.
- [ ] Obtain Wasabi’s explicit candidate sign-off and record the accepted scope and remaining production milestones in the canonical guide.
- [ ] Keep production cutover, physical Raspberry Pi/edge validation, and the deferred Scale profile as separate follow-up milestones unless separately approved and evidenced.

## Evidence locations

Record status and link results in the [candidate completion guide](current-state-and-implementation.md). Relevant supporting records include the [G3 cross-cutting review](g3-cross-cutting-review.md), [G5 provider/source map and open follow-ups](open-follow-ups.md), candidate rollout evidence under [builds](builds/), and the [capability matrix](capability-matrix.md).
