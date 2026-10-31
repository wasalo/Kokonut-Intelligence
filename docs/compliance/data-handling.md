# Data Handling — Classification, Retention & Residency

**Classification:** Internal · **Related:** KI-10 · **Prerequisite for:** KI-8 (Distributed Replicas)
**Status:** Retention periods and legal-hold rules are not configured in the
platform. The current interim policy is no automated pruning. Any future
retention implementation must use an owner-approved, jurisdiction-aware,
configurable policy; pending, processing, retryable, or undisposed dead-letter
records must not be pruned. Residency and production-host statements below
require owner/runtime confirmation before they are used as deployment evidence.

## 1. Data Classification

| Class | Examples | Handling |
|-------|----------|----------|
| Public | Published impact reports, attestations (on-chain) | Open read |
| Internal | Farm operational metrics, pilot datasets | Tenant/operator grants and database boundaries in the Gateway/services; Directus permissions apply only when that adapter is enabled |
| Confidential | Steward PII, wallet mappings, consent records | Least-privilege; encryption-at-rest depends on the selected database/storage deployment and requires verification |
| Restricted | Signing keys, SOPS age key | Kept in operator-controlled secret storage; never committed or exposed to application clients |

## 2. Retention Schedule

| Data | Retention | Basis |
|------|-----------|-------|
| Migration + seed history | Permanent (versioned) | Reproducibility |
| Operational records and metric values | No automated pruning until an approved retention policy is configured | Retention policy must support jurisdiction, record class, legal holds, and documented disposition |
| Event, notification, attempt, and operator-audit records | No automated pruning until approved policy configuration | Pending, processing, retryable, and undisposed dead-letter records are never eligible for pruning |
| Backup snapshots | Set by the active backup deployment policy; not established by this document | Verify production R2/local backup configuration and recovery requirements |
| Consent grants and participant-linked records | No automatic purge; human-reviewed disposition under the approved jurisdictional policy | Withdrawal blocks future use/publication while retention or erasure disposition is reviewed |

## 3. Data Residency

- Primary store and deployment region: confirm from the active deployment
  inventory before making a residency claim. The configured production domain
  planned production hostname is `hub.kokonut.network`; that hostname alone does not establish hosting
  region or residency.
- **Residency rule (KI-8 input):** a replica owns a *disjoint* set of
  `location_id`s; no location's Confidential/Restricted data is replicated
  cross-region without explicit consent grant on record.
- Aggregate-only cross-replica sync: never raw PII, only rolled-up metrics.
- Withdrawal blocks future use and publication. It does not trigger automatic
  deletion: an accountable reviewer must record the applicable retention or
  erasure disposition under the configured policy. Applicable legal basis,
  retention period, and any legal hold require counsel/owner approval.

## 4. Cross-border transfer

Cross-border processor and replica terms require legal and owner review for the
USA and Dominican Republic jurisdictions before deployment. Do not treat the
older DPA/waiver language here as evidence that a current agreement exists.

## 5. Access model (summary; requires deployment-specific verification)

The table below is a data-classification guide, not a complete runtime
authorization inventory. Effective access depends on tenant/operator grants,
database privileges, route policies, and any enabled Directus adapter policies.
Verify each deployment before relying on this summary.

| Role | Public | Internal | Confidential | Restricted |
|------|--------|----------|--------------|------------|
| Anonymous | read | — | — | — |
| Steward | read | write own | read own | — |
| Analyst | read | read | — | — |
| Core Team | read | read/write | read/write | — |
| Agent (Syntropic) | — | propose | — | — |

Full role model: `docs/adelphi-role-circle-governance-pilot.md`,
`docs/agent-access.md`.
