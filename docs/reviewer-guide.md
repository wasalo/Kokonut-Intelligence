# Reviewer Guide

Reviewers protect public trust by checking lifecycle state, evidence maturity, consent, and claim scope before publication.

## Review Checklist

- Confirm records use `draft`, `submitted`, `verified`, `published`, or `rejected` correctly.
- Confirm source lineage fields are populated for evidence-bearing records.
- Confirm public views expose only verified/published and public-safe records.
- Confirm private stakeholder feedback is not leaked into public summaries.
- Confirm public claims include limitations and evidence maturity.

## Carbon Claims

Public carbon claims require:

- `claim_category = 'carbon'`
- `claim_type = 'third_party_verified_claim'`
- `evidence_maturity = 6`
- non-empty `external_verifier`
- non-empty `methodology_ref`
- `status = 'published'`

Level 5 attestations prove a record was attested; they do not equal external verification.

## Dashboards

Use these dashboards before Green Paper publication:

- `dashboards/metabase/20_evidence_gap_dashboard.json`
- `dashboards/metabase/21_stakeholder_feedback_dashboard.json`

## Agent Outputs

Agent-created summaries and tasks must not be verified or published by the agent. Reviewers may use agent drafts as inputs, but final publication remains a human governance decision.
