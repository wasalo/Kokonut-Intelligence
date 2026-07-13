# Credit Lifecycle

Credit issuance custody and carbon-credit retirement are governed but distinct flows.

## Class, Batch, And Custody

```text
credit_class -> batch draft -> submitted -> verified
verified batch + authorized, non-revoked issuer -> published batch
                                                  -> issuer credit_balance.tradable_amount
```

```bash
python3 -m services.credit_class.cli class create --name "Kokonut Carbon" \
  --methodology "IPCC 2006" --type carbon --url https://example.com
python3 -m services.credit_class.cli issuer add --class-id UUID --address 0x1234 --name "Kokonut DAO"
python3 -m services.credit_class.cli batch create --class-id UUID --location-id UUID \
  --vintage 2026 --quantity 100
python3 -m services.credit_class.cli batch issue --batch-id UUID --issuer 0x1234
python3 -m services.credit_class.cli balance batch --batch-id UUID
```

Issuance locks the batch, requires `status = verified`, verifies the issuer authorization has not been revoked, publishes the batch, and credits the issuer's `credit_balance`. `credit_balance` is the custody ledger: tradable, escrowed, and retired amounts must not be inferred from order status alone.

## Marketplace Escrow

```text
seller tradable -> sell-order escrow -> buyer tradable
                                  \-> returned on cancel/expiry
```

Escrow reserves custody for an active order; it is not retirement. Order creation atomically moves quantity from `tradable_amount` to `escrowed_amount`. Execution removes seller escrow and credits the buyer; cancellation or expiry returns escrow. Insufficient or inconsistent balances fail closed under row updates/locks.

## Human-Reviewed Retirement

The governed `services.analytics.carbon_credits` flow reserves first and retires only after independent confirmation:

```text
verified/published carbon_credit
  -> retirement request draft + reserved_tonnes
  -> human confirm -> retirement verified + reserved decreases + retired increases
  -> human reject/cancel -> reserved decreases; no retirement
```

```bash
python3 -m services.analytics.carbon_credits --retire --credit-id UUID --tonnes 5 \
  --reason voluntary_retirement --requested-by REQUESTER_UUID --idempotency-key REQUEST_KEY
python3 -m services.analytics.carbon_credits --confirm-retirement \
  --retirement-id UUID --reviewer-id REVIEWER_UUID
```

Reservations use row locks and availability checks. Stable idempotency keys make repeated requests safe. The requester cannot review their own request. Confirmation, rejection, and cancellation are idempotent once terminal; ledger inconsistency rolls back and returns an error.

## Invariants And Recovery

- A class defines methodology; only a verified batch may be issued; only an authorized issuer may issue it.
- Escrow is reversible custody, never proof of retirement.
- A retirement request does not reduce available retired supply permanently until human confirmation.
- On a failed transaction, inspect batch, balances, order/retirement status, and application logs before retrying. Reuse the original retirement idempotency key.
- Do not manually reconcile one side of a balance move. Correct the cause and run the transactional operation again or apply an audited migration.

Class administrators configure methodologies and issuers; verifiers approve batches; issuers mint; holders trade; an independent reviewer confirms retirement. See [Platform Integrity](platform-integrity.md), [Migrations](migrations.md), and [Metric Verification](metric-verification.md).
