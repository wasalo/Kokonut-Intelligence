"""Digital financial services (accounts, insurance, loans) CLI.

Extracted from services.analytics.digital_finance so the domain module stays focused on
queries/business logic. Reachable via:

    python -m services.analytics.cli_digital_finance --help
"""

from ..common.commands import CommandLine
from .digital_finance import (
    create_account,
    create_insurance_policy,
    create_loan,
    evaluate_insurance_claim,
    file_insurance_claim,
    record_repayment,
    record_transaction,
)

# ============================================================
# CLI
# ============================================================

cli = CommandLine("digital_finance", "Digital financial services")


def _cmd_create_account(db, a):
    return create_account(
        db, a.location_id, a.account_type,
        currency=a.currency, holder_name=a.holder_name,
        provider=a.provider, account_number=a.account_number,
        credit_limit=a.credit_limit,
    )


def _cmd_record_tx(db, a):
    return record_transaction(
        db, a.account_id, a.tx_type, a.amount, a.direction,
        currency=a.currency, description=a.description,
        external_ref=a.external_ref, fee_amount=a.fee,
    )


def _cmd_create_insurance(db, a):
    return create_insurance_policy(
        db, a.location_id, a.product_type, a.coverage, a.premium,
        risk_score=a.risk_score, crop_type=a.crop, area_hectares=a.area,
        coverage_start=a.start, coverage_end=a.end,
        deductible_pct=a.deductible,
    )


def _cmd_file_claim(db, a):
    evidence = json.loads(a.evidence) if a.evidence else None
    return file_insurance_claim(
        db, a.policy_id, a.claim_type, a.amount,
        evidence=evidence, event_date=a.event_date, description=a.description,
    )


def _cmd_evaluate_claim(db, a):
    return evaluate_insurance_claim(
        db, a.claim_id, a.status,
        adjustment=a.adjustment, notes=a.notes, payout_amount=a.payout,
    )


def _cmd_create_loan(db, a):
    return create_loan(
        db, a.location_id, a.amount, a.rate, a.term,
        a.purpose or "working_capital",
        eligibility_score=a.eligibility, currency=a.currency,
    )


def _cmd_repay(db, a):
    return record_repayment(
        db, a.loan_id, a.amount,
        payment_method=a.method, external_ref=a.external_ref,
    )


cli.subcommand("create-account", "Create financial account") \
    .add("--location-id", required=True) \
    .add("--type", required=True, dest="account_type") \
    .add("--currency", default="KES") \
    .add("--holder", dest="holder_name") \
    .add("--provider") \
    .add("--account-number") \
    .add("--credit-limit", type=float, default=0) \
    .add("--json", action="store_true") \
    .run(_cmd_create_account)

cli.subcommand("record-tx", "Record transaction") \
    .add("--account-id", required=True) \
    .add("--type", required=True, dest="tx_type") \
    .add("--amount", type=float, required=True) \
    .add("--direction", required=True) \
    .add("--currency", default="KES") \
    .add("--description") \
    .add("--external-ref") \
    .add("--fee", type=float, default=0) \
    .add("--json", action="store_true") \
    .run(_cmd_record_tx)

cli.subcommand("balance", "Get account balance") \
    .add("--account-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_account_balance(db, a.account_id))

cli.subcommand("list", "List accounts") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: list_accounts(db, a.location_id))

cli.subcommand("create-insurance", "Create insurance policy") \
    .add("--location-id", required=True) \
    .add("--product", required=True, dest="product_type") \
    .add("--coverage", type=float, required=True) \
    .add("--premium", type=float, required=True) \
    .add("--risk-score", type=float) \
    .add("--crop") \
    .add("--area", type=float) \
    .add("--start") \
    .add("--end") \
    .add("--deductible", type=float, default=0) \
    .add("--json", action="store_true") \
    .run(_cmd_create_insurance)

cli.subcommand("file-claim", "File insurance claim") \
    .add("--policy-id", required=True) \
    .add("--type", required=True, dest="claim_type") \
    .add("--amount", type=float, required=True) \
    .add("--evidence", help="JSON evidence data") \
    .add("--event-date") \
    .add("--description") \
    .add("--json", action="store_true") \
    .run(_cmd_file_claim)

cli.subcommand("evaluate-claim", "Evaluate insurance claim") \
    .add("--claim-id", required=True) \
    .add("--status", required=True) \
    .add("--adjustment", type=float, default=0) \
    .add("--notes") \
    .add("--payout", type=float) \
    .add("--json", action="store_true") \
    .run(_cmd_evaluate_claim)

cli.subcommand("create-loan", "Create digital loan") \
    .add("--location-id", required=True) \
    .add("--amount", type=float, required=True) \
    .add("--rate", type=float, required=True) \
    .add("--term", type=int, required=True) \
    .add("--purpose") \
    .add("--eligibility", type=float) \
    .add("--currency", default="KES") \
    .add("--json", action="store_true") \
    .run(_cmd_create_loan)

cli.subcommand("repay", "Record loan repayment") \
    .add("--loan-id", required=True) \
    .add("--amount", type=float, required=True) \
    .add("--method", default="mobile_money") \
    .add("--external-ref") \
    .add("--json", action="store_true") \
    .run(_cmd_repay)

cli.subcommand("portfolio", "Portfolio summary") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_portfolio_summary(db, a.location_id))

cli.subcommand("premium", "Calculate insurance premium") \
    .add("--location-id", required=True) \
    .add("--product", required=True) \
    .add("--coverage", type=float, required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: calculate_insurance_premium(db, a.location_id, a.product, a.coverage))

cli.subcommand("eligibility", "Evaluate loan eligibility") \
    .add("--location-id", required=True) \
    .add("--amount", type=float, required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: evaluate_loan_eligibility(db, a.location_id, a.amount))


def main(argv=None):
    cli.run(argv)


if __name__ == "__main__":
    main()

