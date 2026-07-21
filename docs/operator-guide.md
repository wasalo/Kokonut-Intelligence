# Operator Guide

This guide describes the minimum Green Paper operating flow for Kokonut Adelphi and future pilot farms.

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

- Run `./scripts/compute-metrics.sh` after seed or data refresh. This creates or refreshes draft metric values; it does not verify them.
- Send draft metric IDs to an independent human reviewer. Verification is an explicit `python3 -m services.metrics --verify-value UUID --verified-by REVIEWER_UUID --verification-notes "Reviewed evidence"` action.
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

## Workers And Scheduling

- Run `event-worker` continuously when event-bus delivery is required; check it with `python3 -m services.events --stats` and inspect dead letters before replay or disposition.
- Use `python3 -m services.scheduler.cli --status` and `--list-runs` for the opt-in database scheduler.
- Assign each recurring task to exactly one of worker cron, host cron, or the database scheduler. Running duplicate dispatchers can duplicate ingestion and derived records.
- Worker cron metric commands are one-shot computations. Cron determines frequency; do not wrap the metric command in another loop.
- Set `KOKONUT_METRICS_EXECUTION=host` when `scripts/compute-metrics.sh` must execute in the host environment rather than select a one-shot Compose worker.

## Threatcasting, Backcasting, And Delphi

- Record threats, flags, signals, narratives, horizons, and cascades as decision-support evidence. Do not present scenario probability or cascade risk as a prediction or verified fact.
- Create backcasts from a reviewed narrative, record assumptions and gaps, and retain challenged assumptions. Human approval is required to resolve assumption challenges and to adopt milestones as an operating plan.
- Use principle alignment and path comparison as advisory scores. Review source metrics, manual overrides, costs, timing, risk, and affected-community implications before selecting a path.
- Open a Delphi study only after its scope, panel, item scales, and privacy expectations are documented. Monitor live summaries and stopping criteria, but do not expose attributed reasoning from pseudonymous participants.
- The Delphi facilitator may summarize and draft recommendations. A human UUID must approve a recommendation; the agent cannot approve it.

## Forecasts And Credits

- Running the forecast engine writes outputs and moves `forecast_scenario` to `submitted`, never directly to `verified` or `published`. Route submitted forecasts to human review and label them as projections.
- Credit classes, batches, balances, transfers, and retirements are governed internal records. Batch issuance requires a verified batch and an authorized class issuer, then records the batch as published in the Kokonut ledger.
- Internal issuance, custody, marketplace execution, bridging, or retirement does not by itself establish recognition by Verra, Gold Standard, another external registry, or a jurisdiction. Record external registry identifiers and evidence only after independent confirmation.

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
