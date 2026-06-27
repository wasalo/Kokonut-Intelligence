# Operator Guide

This guide describes the minimum Green Paper V1 operating flow for Kokonut Adelphi and future pilot farms.

## Daily And Weekly Data Entry

- Create operational records in Directus as drafts.
- Submit records when source fields, dates, units, and evidence references are complete.
- Keep private evidence offchain; store only hashes, CIDs, UIDs, transaction hashes, and timestamps in public metadata.

## Stakeholder Feedback Submission

- Always ask for explicit consent before recording feedback.
- Set `consent_given = TRUE` only when the stakeholder agrees to public exposure.
- Set `consent_scope` to `public` for feedback that may appear in public views.
- Keep `consent_scope = private` for feedback that should never leave the platform.
- Feedback requires a minimum 7-day review period before verification.
- Public feedback must have a non-empty `public_summary` and `status = 'published'`.

## Monthly Review

- Run `./scripts/compute-metrics.sh` after seed or data refresh.
- Review public metric summaries for verified-only exposure.
- Review stakeholder feedback dashboard for consent, sentiment, and review coverage.
- Review evidence gap dashboard before making public claims.

## Agent Assistance

Operators can ask agents to prepare draft outputs:

```bash
python3 -m services.agents.feedback_agent --location-id UUID --store
python3 -m services.agents.cids_agent --location-id UUID --summary
```

Agent outputs remain drafts and require human review before publication.

## EBF Scorecards

- Use `exports/templates/ebf_scorecard_template.csv` to prepare scorecard period metadata.
- Use `exports/templates/ebf_evidence_template.csv` to prepare evidence links for each pillar score.
- Run `python3 -m services.scoring --scorecard-id UUID --export internal` to inspect internal scorecard JSON.
- Run `python3 -m services.scoring --scorecard-id UUID --export public` only after the scorecard is published and evidence gates pass.
- Run `python3 -m services.analytics --ebf-portfolio-summary` for a portfolio messy roll-up; do not use it as a farm ranking.
- Keep raw private stakeholder feedback out of public equity narratives.
- Treat agent-generated EBF drafts as working material for reviewers, not final scores.

## Publishing Readiness

- Farm Registry record is verified or published.
- Public feedback has explicit consent and a public summary.
- Public impact claims have evidence maturity >= 4.
- Public carbon claims have evidence maturity 6, external verifier, methodology reference, and published status.
- Report snapshots include limitations, uncertainty notes, negative findings, and affected-community voice where available.
- Public EBF scorecards have seven pillar scores, evidence links, and evidence maturity >= 4.
- Public EBF carbon pillar scores have evidence maturity 6.
