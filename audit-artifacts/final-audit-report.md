# Kokonut Intelligence Security Audit

Date: 2026-07-18
Branch: `chore/full-codebase-audit-remediations`

## Scope

- Python services and tests
- Directus hooks and permission configuration
- Solidity contracts and deployment scripts
- Database/public-view governance
- Event bus, scheduler, ingestion, gateway, sandbox, and export boundaries

## Tooling

- CodeQL CLI 2.26.1
- CodeQL Python queries 1.8.6
- CodeQL JavaScript queries 2.4.1
- Semgrep OSS 1.170.0
- Semgrep Pro was not licensed and was not used
- Aderyn remains incompatible with the repository's current Foundry EVM defaults

Artifacts:

- `static_analysis_codeql_1/python-build.log`
- `static_analysis_codeql_1/javascript-build.log`
- `static_analysis_codeql_1/raw/python-results.sarif`
- `static_analysis_codeql_1/raw/javascript-results.sarif`
- `static_analysis_semgrep_1/raw/results.sarif`

## Verification

- Solidity: 31 tests passed
- Focused Python security/durability tests: 55 passed
- Platform-integrity suite: 248 passed, 1 skipped
- Directus hooks: 60 tests passed
- Directus TypeScript build passed
- Directus permission seed applied successfully to the running PostgreSQL database with `ON_ERROR_STOP=1`
- Live permission queries confirmed location scoping on staff reads/updates and field-worker creates

## Remediations

- Added governed public financial views with verified/published gating.
- Removed public metric computation writes from the gateway.
- Added tracked-secret CI scanning.
- Added MQTT HMAC verification and topic/device binding.
- Disabled unsafe production sandbox subprocess execution.
- Replaced unsafe XML parsing and unrestricted expression evaluation.
- Added harvest URL SSRF protections.
- Made workflow authorization fail closed.
- Added append-only consent protections.
- Added Directus tenant scopes and relational reference validation.
- Added event-handler and scheduler execution allowlists.
- Added KGP pause protection to reversals.
- Hardened upgrade scripts with chain, bytecode, timelock, and registry checks.
- Hardened deployment bootstrap handoff and role assertions.
- Removed raw exception disclosure from the HTTP sensor receiver.
- Redacted health-check and Copernicus authentication failure responses/logs.
- Added UUID validation for gateway location proxy paths.
- Added a maximum SPARQL query length to bound parser work.

## Static Analysis Triage

Semgrep produced 24 findings after the final remediation pass. The reviewed results were primarily credential-log heuristics, configuration-controlled URL checks, safe XML export patterns, and write-only pickle model persistence requiring context review. No additional confirmed high-impact issue was identified beyond the remediations above.

CodeQL produced 957 Python and 26 JavaScript alerts including vendored and generated code. After excluding `contracts/lib`, `node_modules`, and `dist`, the relevant security subset was small; most remaining alerts were quality findings such as unused imports, cyclic imports, or test-file resource handling. The HTTP sensor stack-trace disclosure was confirmed and fixed; the rebuilt database reports zero remaining stack-trace alerts.

The remaining first-party security-pattern alerts were reviewed individually:

- API-key SHA-256 hashing is an indexed lookup for high-entropy random tokens, not password storage.
- SQL-injection alerts target the parameterized PostgreSQL adapter wrapper and do not identify interpolated values.
- Logging alerts identify operational IDs, coordinates, filenames, and audit metadata rather than credential material; CLI output is intentionally user-facing.
- Dynamic URL alerts use operator-controlled service configuration, not request-controlled URLs.
- Pickle is used only to serialize locally generated ML models; no untrusted model loading path exists.
- XML alerts are output-only `ElementTree` construction; untrusted XML parsing uses `defusedxml`.
- ClickHouse uses HTTP inside the private Compose network; external TLS termination is handled by the deployment boundary.

The CodeQL JavaScript result was dominated by vendored `contracts/lib` files; the only project result was a low-impact redundant assignment.

## Residual Risks

- CodeQL and Semgrep Pro cross-file analysis were unavailable.
- Live Chiado/Gnosis deployment and fork verification remain outstanding.
- The ignored GEE service-account key must be rotated by an operator if it has ever held real credentials.
- Static-analysis artifacts are intentionally untracked pending review/package decisions.
