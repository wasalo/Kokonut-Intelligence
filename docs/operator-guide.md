# Operator Guide

This guide describes the minimum operating flow for Kokonut Adelphi and future pilot farms. PostgreSQL/Directus is the canonical operational record; ClickHouse is the analytical event store.

## Bootstrap And Recovery

Use encrypted secrets when available. Do not copy decrypted secrets into files, logs, tickets, or commits.

```bash
source scripts/load-secrets.sh
docker compose up -d
./scripts/seed.sh
./scripts/seed-pilot.sh
./scripts/compute-metrics.sh
./scripts/verify-platform.sh
```

- `scripts/compute-metrics.sh` computes draft, unverified metric values. It is not a verification step.
- Set `KOKONUT_METRICS_EXECUTION=host` when metric computation must run on the host; otherwise the script selects a one-shot Compose worker.
- Check service state with `docker compose ps` and logs with `docker compose logs SERVICE`.
- Run `./scripts/backup.sh` before migrations or destructive maintenance and test the backup before relying on it.
- Run `python3 -m services.migration status`, then `dry-run`, then `migrate`. Run one migration process at a time. Never edit an applied migration; add a new migration instead.
- The migration status and dry-run commands reconcile the tracking table, so they are not strictly read-only database operations.
- If a migration fails, inspect database state and `schema_migration` before retrying. Repository SQL can contain transaction control and may be partially committed.
- Use `./scripts/schema-snapshot.sh` for a Directus schema snapshot. Access databases through Compose service names, not undocumented host ports.
- Run `./scripts/health-check.sh --json` for machine-readable service and resource health; add `--alert` only when alert delivery is configured.

## Daily And Weekly Data Entry

- Create operational records in Directus as `draft`.
- Submit records only when source fields, dates, units, lineage fields, and evidence references are complete.
- Use `verified` and `published` only through the applicable human review workflow. `rejected` means rework or exception, not payment failure.
- Keep private evidence offchain; store only hashes, CIDs, UIDs, transaction hashes, and timestamps in public metadata.
- Check required source fields on pilot `expense_event` and `harvest_event` rows: `source_system`, `source_id`, and `source_raw`.

## Stakeholder Feedback

- Ask for explicit consent before recording feedback and keep feedback private by default.
- `consent_given = TRUE` records consent; it does not by itself make a record public.
- For `stakeholder_feedback`, use the schema’s `consent_scope` values: `private_review`, `public_summary`, `public_quote`, or `public_full`.
- Set `is_public = TRUE` only when consent is explicit, the scope is public-safe, `public_summary` is non-empty, and the record is `published`.
- Feedback verification requires a minimum seven-day review period after submission.
- The feedback agent uses public summaries and aggregates private/no-consent signals; it must never expose raw private feedback.
- Review `docs/common-foundations-checklist.md` and `docs/reviewer-guide.md` before public export.

## Monthly Review

- Run `./scripts/compute-metrics.sh` after seed or data refresh.
- Send draft metric IDs to an independent human reviewer. Verify explicitly:

```bash
python3 -m services.metrics --verify-value UUID \
  --verified-by REVIEWER_UUID \
  --verification-notes "Reviewed evidence"
```

- Review public metric summaries for verified-only exposure and confirm the farm registry record is verified or published.
- Review stakeholder feedback for consent, public-safe scope, sentiment, review coverage, and unresolved harms or unintended consequences.
- Review the evidence-gap and stakeholder-feedback dashboards before making public claims.
- Public reports must include limitations and uncertainty. Preserve negative findings and affected-community voice where available; do not cherry-pick favorable evidence.

## Agent Assistance

Agents may prepare read-only outputs or draft governed records:

```bash
python3 -m services.agents.feedback_agent --location-id UUID --store
python3 -m services.agents.ai_summary --location-id UUID --summary-type combined --store
python3 -m services.agents.cids_agent --location-id UUID --summary
python3 -m services.agents.open_source_capitalist_agent --location-id UUID --store
```

- `--store` writes a draft for human review; without it, summary agents do not persist the output.
- Agents cannot verify or publish governed records, approve recommendations, attest, submit onchain actions, or autonomously execute financial or destructive actions.
- Check the task catalogue in `services/agents/tasks.py` for each agent’s inputs, outputs, writes, and risk classification.
- Treat agent-generated summaries, EBF drafts, recommendations, tactical opportunities, and credit proposals as advisory or draft material until a human completes the applicable workflow.

## Workers, Scheduler, And Events

- Assign each recurring task to exactly one of worker cron, host cron, or the opt-in database scheduler. Duplicate dispatchers can duplicate ingestion and derived records.
- Worker cron metric commands are one-shot computations. Cron determines frequency; do not wrap the metric command in another loop.
- Inspect scheduler state and runs:

```bash
python3 -m services.scheduler.cli --status
python3 -m services.scheduler.cli --list-runs
python3 -m services.scheduler.cli --worker --tick-interval 30
```

- Use `--enable TASK`, `--disable TASK`, `--tick`, or `--run-now TASK` deliberately. `--run-now` is a diagnostic/manual execution and still must respect task idempotency and leases.
- Scheduler claims use database leases and row locking. Preserve non-overlap, retry/backoff, expired-lease recovery, and durable run state when troubleshooting.
- Run the event bus continuously when delivery is required:

```bash
python3 -m services.events --worker
python3 -m services.events --stats
python3 -m services.events --list-handlers
python3 -m services.events --list-dead-letter
```

- Event delivery uses leases, bounded retries, and dead-letter disposition. Inspect the dead-letter record and reason before replaying it:

```bash
python3 -m services.events --replay-dead-letter --event-id UUID --actor OPERATOR
python3 -m services.events --dispose-dead-letter --event-id UUID \
  --disposition resolved --actor OPERATOR --reason "Fixed upstream"
```

- Use `--process` for a bounded processing pass, `--cleanup` for retention cleanup, and `--batch-size`/`--lease-seconds` only with an operational reason.

## Threatcasting, Backcasting, And Delphi

- Treat threats, flags, signals, narratives, horizons, cascades, and probabilities as decision-support evidence, not verified predictions.
- Create backcasts from a reviewed narrative; retain assumptions, gaps, and challenged assumptions. Human approval is required to resolve challenges and adopt milestones as an operating plan.
- Use principle alignment and path comparison as advisory scores. Review source metrics, manual overrides, cost, timing, risk, and affected-community implications before selecting a path.
- Open a Delphi study only after documenting its scope, panel, scales, and privacy expectations. Monitor live summaries and stopping criteria without exposing attributed reasoning from pseudonymous participants.
- The Delphi facilitator may summarize and draft recommendations. A human UUID must approve a recommendation; the agent cannot approve it.

## Forecasts And Credits

- Forecast execution writes outputs and moves `forecast_scenario` to `submitted`, never directly to `verified` or `published`. Label submitted results as projections and route them to human review.
- Credit classes, batches, balances, transfers, and retirements are governed internal records. Batch issuance requires a verified batch and authorized class issuer.
- Retirement reserves quantity atomically and requires independent human confirmation before final balance mutation or certificate use.
- Internal issuance, custody, marketplace execution, bridging, or retirement does not establish recognition by Verra, Gold Standard, another registry, or a jurisdiction. Add registry identifiers and evidence only after independent confirmation.

## EBF Scorecards

- Use `exports/templates/ebf_scorecard_template.csv` for scorecard period metadata and `exports/templates/ebf_evidence_template.csv` for pillar evidence links.
- Inspect internal or public scorecard JSON:

```bash
python3 -m services.scoring --scorecard-id UUID --export internal
python3 -m services.scoring --scorecard-id UUID --export public
```

- Export public scorecards only after publication and evidence gates pass. Public scorecards require seven pillar scores, evidence links, and evidence maturity at least 4; the carbon pillar requires the stricter Level 6 carbon gate.
- Use `python3 -m services.analytics --ebf-portfolio-summary` for a confidence-labelled portfolio roll-up, not a farm ranking.
- Keep raw private stakeholder feedback out of public equity narratives.

## Publishing Readiness

- Farm registry record is verified or published.
- Public feedback has explicit consent, a public-safe `consent_scope`, non-empty `public_summary`, and `status = 'published'` with `is_public = TRUE`.
- Public impact claims have evidence maturity at least 4.
- Public carbon claims have evidence maturity 6, `claim_category = 'carbon'`, qualifying carbon claim type, external verifier, methodology reference, and published status.
- Public EBF scorecards have seven pillar scores, evidence links, and evidence maturity at least 4.
- Public EBF carbon pillar scores have evidence maturity 6 and a qualifying linked carbon claim.
- Report snapshots include limitations, uncertainty notes, negative findings, and affected-community voice where available.
- Review `docs/common-foundations-checklist.md`, `docs/evidence-maturity.md`, and `docs/public-report-disclaimer.md` before publication.

## Verification Commands

Run focused integrity checks after changing operational configuration or governance rules:

```bash
python3 -m pytest \
  tests/test_scheduler_durability.py \
  tests/test_event_bus_durability.py \
  tests/test_agent_safety.py \
  tests/test_agent_tasks.py \
  tests/test_common_foundations.py \
  tests/test_delphi.py \
  tests/test_threatcasting.py \
  tests/test_backcasting_enhancements.py \
  tests/test_carbon_credits.py \
  tests/test_platform_done.py -v
```

These tests validate behavior; they do not replace human review, evidence inspection, or publication approval.
