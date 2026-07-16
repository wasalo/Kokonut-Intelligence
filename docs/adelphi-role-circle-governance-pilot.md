# Adelphi Role-and-Circle Governance Pilot

## Purpose

This pilot evaluates a Kokonut-native role-and-circle governance model inspired
by selected Holacracy concepts. It is an extension of the existing stakeholder,
RACI, consent, grievance, decision, coordination, workflow, and agent-safety
systems. It is not a replacement for treasury governance, Colony Guild
execution, or existing human approval boundaries.

## Pilot Scope

- Pilot identity: Kokonut Adelphi
- Initial circle: Adelphi Stakeholder Stewardship
- Initial adjacent concerns: ecological stewardship, market relationships, and
  evidence and measurement
- Initial users: human stakeholder stewards, relationship owners, evidence
  custodians, grievance owners, and authorized reviewers
- Initial records: role definitions, role assignments, stakeholder tensions,
  linked work items, and governance observations

## Non-Goals

- Do not replace Gnosis/Moloch treasury governance.
- Do not replace Colony Guild execution or reputation records.
- Do not remove human approval from publication, financial, attestation,
  proxy-authority, ecological-impact, or material-harm decisions.
- Do not require every party, team, or stakeholder to belong to a circle.
- Do not grant agents authority to activate circles, assign roles, change
  domains, resolve objections, approve proposals, or publish governance
  records.
- Do not introduce unrestricted blanket authority or consensus-by-default.

## Pilot Principles

- Roles describe purpose and ongoing accountabilities; people and parties fill
  roles temporarily and explicitly.
- Circles are bounded by purpose, scope, domain, and review dates.
- Existing RACI assignments remain the entity-level accountability mechanism.
- Governance changes are separate from operational work.
- Tensions are observable coordination gaps that should become owned actions,
  work items, or governance proposals.
- Consent, minority views, grievances, ecological interests, and future
  generations remain governed through their existing controls.
- Every structural change has an owner, evidence, human review, and a review
  date.

## Baseline At Phase 0

- PR 15, `feat: close coordination governance gaps`, was merged into `main`.
- Merged commit: `519e8e1`.
- Migrations: all applied successfully.
- Stakeholder baseline: `23 passed`.
- Coordination, workflow, agent-safety, migration, and platform baseline:
  `60 passed`.
- The combined unbounded baseline command exceeded the local 120-second
  timeout during a coordination test; the affected coordination test passed
  when isolated, and the bounded suites completed successfully.

## Phase 1 Entry Criteria

Phase 1 may begin only after:

- the pilot circle purpose is approved by a human reviewer;
- the initial human role holders are identified;
- the role authority domains and constraints are documented;
- the pilot data remains internal by default;
- the next migration is additive and checksum-safe;
- agent draft-only behavior is covered by tests;
- the pilot has a named review owner and review date.

## Initial Role Candidates

- Stakeholder Steward: maintain affected-party interests, representation,
  consent, and follow-through.
- Circle Steward: maintain circle purpose, scope, role coverage, and review
  health.
- Evidence Custodian: maintain evidence lineage, verification state, and
  uncertainty notes.
- Consent Custodian: verify consent before engagement, publication, or data
  use.
- Grievance Owner: coordinate acknowledgement, investigation, remedy, and
  closure.
- Ecological Proxy Steward: maintain nature and future-generation proxy
  authority and review.
- Market Relationship Owner: coordinate buyer, cooperative, and partner
  commitments.
- Governance Facilitator: facilitate structured governance sessions without
  owning substantive decisions.
- Governance Recorder: maintain proposal, objection, decision, and outcome
  records.

## Pilot Measures

- active roles with current human assignments;
- roles with explicit purpose and authority domains;
- unresolved tensions by age and severity;
- time from tension report to triage and owned action;
- overdue stakeholder commitments;
- unresolved consent, harm, grievance, and minority-view gates;
- governance administration time per review cycle;
- agent drafts accepted, modified, and rejected;
- decisions reversed after implementation.

These are coordination indicators. They must not be represented as direct
evidence of stakeholder wellbeing, ecological improvement, or public impact
without separate governed outcome evidence.

## Review

The pilot should be reviewed after the first bounded operating cycle. Expansion
to additional circles requires evidence that role clarity and tension handling
improved coordination without bypassing existing safeguards or creating
unacceptable administrative overhead.
