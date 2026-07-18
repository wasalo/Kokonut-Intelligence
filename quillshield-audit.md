# QuillShield Codebase-Wide Security Audit

**Date:** 2026-07-17
**Baseline:** Current working tree, including uncommitted Solidity fixes and audit reports
**Scope:** Solidity, Python services, PostgreSQL/ClickHouse schemas, Directus hooks, Compose, CI, scripts, and deployment documentation

## Classification

| Area | Trust boundary | Primary risk |
| --- | --- | --- |
| Solidity | EOA/multisig/timelock -> contracts -> EAS | upgrades, reputation integrity, governance |
| Gateway/API | network clients -> FastAPI/Directus/DB | authorization, tenant isolation, public data |
| Ingestion | devices/brokers/APIs -> PostgreSQL/ClickHouse | spoofing, poisoning, actuation inputs |
| Sandbox/agents | database/config -> subprocesses | arbitrary code and secret access |
| Database | services/Directus -> governed records/views | lifecycle, consent, public exposure |
| CI/deployment | pull requests/build hosts -> Docker/secrets | supply-chain and host compromise |

## Findings

### F-01: HTTP Sensor Receiver Does Not Verify Signatures

**Severity:** High | **Confidence:** 95%
**Location:** `services/ingestion/http_sensor_receiver.py:159-185`

The receiver defines HMAC verification but never calls it. Missing, invalid, and arbitrary signatures are accepted; batch ingestion has no verification path.

**Exploit:** POST forged readings or device data to either endpoint -> PostgreSQL and ClickHouse accept the records -> metrics, anomaly detection, and downstream decisions consume attacker-controlled data.

**Impact:** Sensor integrity and automated decision inputs can be poisoned without device credentials.

**Fix:** Require a device secret and valid constant-time HMAC for single and batch requests. Sign the exact raw request body and bind the device identity to the path and payload.

### F-02: MQTT Sensor Ingestion Allows Anonymous Registration and Data Injection

**Severity:** High | **Confidence:** 95%
**Location:** `config/mosquitto/mosquitto.conf:4-7`, `services/ingestion/mqtt_subscriber.py:55-131`

MQTT permits anonymous access, and the subscriber auto-registers devices and accepts readings without client authentication, message signatures, topic ACLs, or topic/payload identity binding.

**Exploit:** Connect to the broker -> publish to registration or readings topics -> create active devices or poison readings and device-health state.

**Impact:** Untrusted actors with broker/network access can corrupt analytical and actuation inputs.

**Fix:** Require TLS/client authentication, topic ACLs, signed payloads, explicit registration approval, and strict topic/device identity matching.

### F-03: Sandbox Execution Is Not an Isolation Boundary

**Severity:** High | **Confidence:** 95%
**Location:** `services/sandbox/environment.py:94-129`

`module_path` is executed directly with the service interpreter and inherits filesystem, environment, network, database credentials, and process privileges. `IsolationGuard` only validates SQL text and is not invoked by `run()`.

**Exploit:** Submit an importable module path -> subprocess executes it -> module reads secrets, databases, files, or network resources.

**Impact:** Arbitrary Python code execution for any caller who reaches sandbox execution.

**Fix:** Execute only signed/allowlisted modules inside a separate restricted container or worker with dropped privileges, read-only filesystem, no credentials, network policy, CPU/memory/pid limits, and enforced database credentials.

### F-04: Stakeholder Feedback Verification Fails Open

**Severity:** High | **Confidence:** 95%
**Location:** `extensions/kokonut-hooks/src/workflow.ts:297-318`

Database lookup failures during the mandatory seven-day review check are caught and treated as permission to continue.

**Exploit:** Cause the lookup to fail or become unavailable -> transition proceeds without the review-period evidence -> feedback can be verified prematurely.

**Impact:** Governed stakeholder evidence can bypass its required review period during database or query failures.

**Fix:** Fail closed on lookup, parsing, or database errors. Allow only an explicit, separately audited emergency workflow with human approval.

### F-05: Consent Withdrawal Can Resurface an Older Grant

**Severity:** High | **Confidence:** 95%
**Location:** `services/analytics/data_governance.py:131-153`, `:185-234`

Legacy consent queries exclude withdrawn records before selecting the latest event. After withdrawing the newest grant, an older grant can become the selected active row. `check_consent()` also uses `consent_method` instead of `effective_status` when computing `consented` and returning the effective status.

**Exploit:** Grant consent -> withdraw the newest grant -> query consent status -> older grant remains eligible.

**Impact:** Data use or sharing can continue after withdrawal, violating the consent boundary.

**Fix:** Select the latest event including withdrawals, then derive effective state. Use the effective-status column consistently and add withdrawal regression tests.

### F-06: Future-Dated Consent Events Become Effective Immediately

**Severity:** High | **Confidence:** 90%
**Location:** `schemas/postgres/215_stakeholder_consent.sql:47-90`

The effective-consent view selects the latest event by `effective_at` but does not exclude events whose effective time is in the future.

**Exploit:** Insert a future grant or withdrawal with a later `effective_at` -> view selects it immediately -> services consume its status before the intended time.

**Impact:** Consent can be granted or withdrawn ahead of its authorized effective time.

**Fix:** Filter `effective_at <= NOW()` in the effective view, or select the latest event among currently effective events and separately expose scheduled events.

### F-07: Public Gateway Metrics Return Fresh Unverified Computations

**Severity:** High | **Confidence:** 85%
**Location:** `services/gateway/router.py:89-102`, `services/metrics/engine.py:108-142`

The route is explicitly public and calls `compute_all()`, which creates or returns computed metric results without requiring verified metric values or a verified/published farm registry record.

**Exploit:** Request `/api/metrics/{location_id}` anonymously -> service computes and returns current metrics -> unverified/private data becomes public.

**Impact:** Public APIs can expose ungoverned metrics and create draft records as a side effect of anonymous reads.

**Fix:** Public routes must read only governed public views. Require verified/published registry state and verified metric values; never compute or write from an anonymous GET.

### F-08: Public Financial Views Bypass Registry and Governance Gates

**Severity:** High | **Confidence:** 95%
**Location:** `schemas/postgres/063_statement_of_work.sql:165-170`, `:192-198`, `:219-225`; `schemas/postgres/098_multi_farm.sql:80-87`

Public SOW views use `(fr.id IS NULL OR fr.status IN (...))`, exposing locations without any registry record. The portfolio view exposes all `cross_farm_portfolio` data and aggregates all revenue events without lifecycle, tenant, registry, or verification filters.

**Impact:** Financial contracts, schedules, portfolio totals, and ungoverned revenue can be publicly exposed.

**Fix:** Require an existing verified/published registry record, filter lifecycle and consent state, scope by authorized/public location, and aggregate only verified/public financial events.

### F-09: OneDev Pull-Request Builds Execute Untrusted Code on the Host With Secrets

**Severity:** High | **Confidence:** 90%
**Location:** `.onedev-buildspec.yml:14-33`, `:51-70`, `:78-83`

Pull-request builds run with `runInContainer: false`, create `.env` secrets, install packages, execute repository scripts, and access Docker. A dynamic `curl` downloads Docker Compose from `releases/latest` without checksum or signature verification.

**Impact:** A malicious PR can exfiltrate CI secrets, access the Docker host, or compromise build infrastructure.

**Fix:** Run PR builds in isolated ephemeral containers/runners without deployment secrets or Docker socket access. Pin and verify downloaded tools and require approval for privileged builds.

### F-10: Production Redis Uses a Known Password Fallback

**Severity:** Medium | **Confidence:** 95%
**Location:** `docker-compose.yml:23-30`, `:65-70`

Redis falls back to `changeme` when `REDIS_PASSWORD` is absent.

**Impact:** Any process on the database network can authenticate and manipulate cache/session/rate-limit state.

**Fix:** Make `REDIS_PASSWORD` mandatory with Compose interpolation errors; reject placeholders at startup.

### F-11: gRPC API-Key Authentication Is Unencrypted in Base Compose

**Severity:** Medium | **Confidence:** 95%
**Location:** `docker-compose.yml:156-174`, `services/grpc/server.py:93`

The service binds broadly and publishes port `50051` while API keys are transported over insecure gRPC.

**Impact:** Network observers can capture credentials and impersonate clients.

**Fix:** Use TLS/mTLS, bind privately by default, and expose only through an authenticated reverse proxy or private network.

### F-12: Backups Are Plaintext and Can Report Success After Data Loss

**Severity:** Medium | **Confidence:** 90%
**Location:** `scripts/backup.sh:15-28`, `:40-78`

Backups are stored unencrypted under the project directory. ClickHouse schema/data failures are suppressed with `|| true`, while the script still prints completion.

**Impact:** Sensitive data is exposed to filesystem readers and operators may retain incomplete backups believing they are valid.

**Fix:** Encrypt backups, set restrictive permissions, write outside the application tree, fail on any dump error, validate archive contents, and perform restore tests.

### F-13: Capability Token Usage Limits Are Raceable

**Severity:** Medium | **Confidence:** 90%
**Location:** `services/security/capabilities.py:123-149`

The code checks `usage_count` and then increments it in a separate unconditional update. Concurrent requests can pass the same limit check.

**Impact:** Bounded-use or one-time capability tokens can be accepted more times than configured.

**Fix:** Use an atomic conditional update such as `UPDATE ... SET usage_count = usage_count + 1 WHERE id = %s AND usage_count < max_usage RETURNING ...`.

### F-14: Portability Fulfillment Authorization Is Self-Asserted

**Severity:** Medium | **Confidence:** 80%
**Location:** `services/analytics/data_governance.py:435-469`

`fulfilled_by` and `authorization_ref` are only required to be non-empty. No role, actor, or authorization record is validated.

**Impact:** A caller able to reach the function can mark a data-export request ready with fabricated fulfillment authority.

**Fix:** Resolve the authenticated actor, require an authorized fulfillment role, validate the authorization reference against a governed approval, and audit the actor.

### F-15: Production Deployment Lacks Fork Rehearsal and Static Analysis Gates

**Severity:** High release blocker | **Confidence:** 100%
**Location:** `docs/kgp-deployment.md`, `contracts/script/*.s.sol`, repository CI configuration

No Chiado/Gnosis fork rehearsal, deployment manifest verification, post-deploy role snapshot, or storage-diff gate was found. Slither, Aderyn, Mythril, Echidna, Semgrep, Bandit, Trivy, and Solhint were unavailable in the audit environment.

**Impact:** Deployment and upgrade misconfiguration can reach a live network without validated chain addresses, storage migration, role custody, or security-tool coverage.

**Fix:** Block mainnet release until fork deployment, upgrade migration, storage diff, role/ownership assertions, event checks, smoke tests, static analysis, and restore/recovery rehearsals pass.

## Lower-Risk Hardening

- `services/ingestion/harvest_manager.py:14-22` accepts arbitrary URLs without SSRF validation.
- `extensions/kokonut-hooks/src/workflow.ts:214-225` returns true for unregistered collections; unknown collections should fail closed.
- `services/analytics/data_governance.py:91-116` and canonical consent withdrawal lack actor/ownership authorization.
- `config/caddy/Caddyfile:5-6` always uses `tls internal`, conflicting with production certificate documentation.
- Shell scripts use `source`/`eval` with environment-derived content.
- Docker images, GitHub Actions, and Python dependencies are not consistently pinned by digest/hash.
- No stateful invariants cover credit custody, workflow transitions, or KGP/task/review state machines.

## Verification

- Solidity: 30 Foundry tests passed; build and size checks passed.
- Python focused suite: 247 passed, 1 skipped.
- Static tools unavailable: Semgrep, Bandit, pip-audit, Trivy, Slither, Aderyn, Mythril, Echidna, Solhint.
- No secrets were decrypted or displayed.
- Audit did not modify source code; this report is the only new audit artifact.

## Defender Verdict

**VERDICT: BLOCK DEPLOY**

Top blockers:

- Unauthenticated sensor and MQTT ingestion can poison governed data and automated decisions.
- Sandbox execution permits arbitrary code with service credentials.
- Lifecycle and consent controls fail open or can be bypassed.
- Public APIs/views expose unverified or ungoverned data.
- PR CI executes untrusted code on the host with secrets.
- Mainnet deployment lacks fork rehearsal and release-gate evidence.

Required before release:

- Fix F-01 through F-09 and F-15.
- Add regression tests for consent, public data gates, sensor authentication, sandbox isolation, and workflow fail-closed behavior.
- Add fork-level deployment/upgrade tests and role/address/storage manifests.
- Run static analysis in isolated CI with pinned tools and dependency hashes.
