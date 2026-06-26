# Reporting Principles

Kokonut Green Paper reports should be useful to partners without overstating evidence quality or exposing private stakeholder evidence.

## Public-Interest Defaults

- Public reports use governed records and public-safe summaries, not raw private evidence.
- Stakeholder feedback is private by default. Public reports may include it only when consent is explicit and scoped for public use.
- Positive claims should be paired with limitations, evidence gaps, and uncertainty notes.
- Public carbon claims require Evidence Maturity Level 6, external verifier text, methodology reference, and published status.
- CIDS export is a compatibility layer; PostgreSQL and Directus remain the canonical record of governance, consent, and evidence maturity.

## Report Snapshot Fields

`services/export/report_generator.py` attaches a `public_interest` section to generated report data and writes the following `report_snapshot` fields when available:

- `public_interest_summary`
- `uncertainty_notes`
- `negative_findings`
- `affected_community_voice`

## Dashboard Review

Use the Evidence Gap and Stakeholder Feedback dashboards before publishing Green Paper materials. Claims with missing evidence links, public claims below maturity thresholds, or carbon claims below Level 6 should be treated as review items rather than public proof.
