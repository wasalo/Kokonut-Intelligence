# Data Handling — Classification, Retention & Residency

**Classification:** Internal · **Related:** KI-10 · **Prerequisite for:** KI-8 (Distributed Replicas)
**Note:** KI-8 shards by `location_id`; the residency rules here MUST be
finalized before edge replicas are deployed.

## 1. Data Classification

| Class | Examples | Handling |
|-------|----------|----------|
| Public | Published impact reports, attestations (on-chain) | Open read |
| Internal | Farm operational metrics, pilot datasets | Role-gated (Directus) |
| Confidential | Steward PII, wallet mappings, consent records | Encrypted at rest, least-privilege |
| Restricted | Signing keys, SOPS age key | Host-only; never leaves `cerberus` |

## 2. Retention Schedule

| Data | Retention | Basis |
|------|-----------|-------|
| Migration + seed history | Permanent (versioned) | Reproducibility |
| Operational metrics (draft) | 90d then purged if unverified | Storage hygiene |
| Verified/published metrics | Life of farm + 7y | Audit |
| Event bus (ClickHouse) | 2y hot, 5y cold | Analytics |
| Backup snapshots | 7d on-host, 30d off-host | DR (prod policy) |
| Consent grants | Life of subject + 1y | GDPR Art.17 |

## 3. Data Residency

- Primary store: `cerberus` (EU-adjacent VPS). Pilot data = Adelphi,
  Monte Plata, Dominican Republic.
- **Residency rule (KI-8 input):** a replica owns a *disjoint* set of
  `location_id`s; no location's Confidential/Restricted data is replicated
  cross-region without explicit consent grant on record.
- Aggregate-only cross-replica sync: never raw PII, only rolled-up metrics.
- Right-to-erasure (GDPR Art.17): consent revocation triggers cascade
  purge of `stakeholder_feedback` + linked PII within SLA.

## 4. Cross-border transfer

Transfers to EU/EEA processors (Celo EAS, hosting) governed by standard
contractual clauses. Non-EEA replica requires DPA + residency waiver signed
by Core Team before `location_id` assignment.

## 5. Access matrix (summary)

| Role | Public | Internal | Confidential | Restricted |
|------|--------|----------|--------------|------------|
| Anonymous | read | — | — | — |
| Steward | read | write own | read own | — |
| Analyst | read | read | — | — |
| Core Team | read | read/write | read/write | — |
| Agent (Syntropic) | — | propose | — | — |

Full role model: `docs/adelphi-role-circle-governance-pilot.md`,
`docs/agent-access.md`.
