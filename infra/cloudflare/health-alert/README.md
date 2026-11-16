# Candidate health email monitor

This scheduled Worker adds a direct email path for the candidate readiness
endpoint while Better Stack remains the independent external monitor. It is
not an acknowledged pager and does not automate escalation. The accepted
recipient is `alejandro@kokonut.network`; existing application event mail to
`intelligence@kokonut.network` remains a separate flow.

## Behavior

- Runs once per minute and checks only
  `https://hub.kokonut.network/health/ready`.
- A readiness response must be HTTP 200 JSON with `{"status":"ready"}`.
  Redirects, malformed/oversized bodies, timeouts, and other responses count
  as failed observations. The Worker reveals no health detail publicly.
- Sends one outage email after two continuous minutes of failed checks.
- Sends one recovery email after five continuous minutes of healthy checks.
- Uses one SQLite-backed Durable Object for durable state and the pending
  email outbox. Each notification gets at most three attempts; temporary
  provider errors wait five minutes and then fifteen minutes before retrying.
  It never sends repeat emails just because an outage continues.
- Persists each attempt before calling Maileroo. If the Worker restarts after
  claiming the final attempt but before persisting its result, the delivery is
  recorded as uncertain and abandoned rather than risk a duplicate email.
- Logs only health status, HTTP status, transition, and bounded delivery
  outcome. It does not log addresses, email bodies, provider response bodies,
  or credentials.
- There is no public Worker route. The scheduled entry point calls the
  Durable Object internally.

Maileroo's API key must be a sending key, not an account-management key. In
Cloudflare, store it as the Worker secret `MAILEROO_API_KEY`; source it from
the encrypted `EMAIL_SENDING_KEY` in `.env.sops`, without printing it. The
sender uses `ALERT_EMAIL_FROM` (`auth@mail.kokonut.network`) and the recipient
is configured as `ALERT_EMAIL_TO`.

## Local build check

Run the isolated transition/retry state-machine tests (no Cloudflare or
Maileroo requests are made):

```sh
node --test tests/test_health_alert_monitoring.mjs
```

From the repository root:

```sh
WRANGLER_LOG_PATH=/private/tmp/kokonut-wrangler-logs \
  apps/frontend/node_modules/.bin/wrangler \
  --config infra/cloudflare/health-alert/wrangler.jsonc deploy --dry-run
```

Deploy after the exact source revision has passed repository CI and Security:

```sh
WRANGLER_LOG_PATH=/private/tmp/kokonut-wrangler-logs \
  apps/frontend/node_modules/.bin/wrangler \
  --config infra/cloudflare/health-alert/wrangler.jsonc deploy
```

Set `MAILEROO_API_KEY` through Wrangler's secret input, sourcing only the
`EMAIL_SENDING_KEY` assignment from SOPS. Never put its value in this file,
the command line, or a log. Then confirm the Cron Trigger is active and invoke
one explicit test email to Alejandro; do not create a synthetic outage on the
production health endpoint to test email delivery.

The Worker check cadence is one minute; its two-minute confirmation can issue
email earlier than Better Stack's three-minute monitor with its own
two-minute confirmation. They are independent checks of the same readiness
contract. Email receipt is not acknowledgement; the existing manual five-
minute primary/backup contact procedure remains necessary until an
acknowledged paging channel is approved and exercised.
