#!/usr/bin/env python3
"""
Digital Financial Services

Savings, credit, insurance, and lending built on top of
farm data, CRISP risk scores, and digital twin predictions.

Usage:
    python -m services.analytics.digital_finance create-account --location-id UUID --type savings --currency KES --holder "John Doe"
    python -m services.analytics.digital_finance record-tx --account-id UUID --type deposit --amount 5000 --direction credit
    python -m services.analytics.digital_finance balance --account-id UUID
    python -m services.analytics.digital_finance list --location-id UUID
    python -m services.analytics.digital_finance create-insurance --location-id UUID --product weather_index --coverage 100000 --premium 5000
    python -m services.analytics.digital_finance file-claim --policy-id UUID --type drought --amount 20000 --evidence '{"rainfall_deficit": 40}'
    python -m services.analytics.digital_finance evaluate-claim --claim-id UUID --status approved --adjustment 0
    python -m services.analytics.digital_finance create-loan --location-id UUID --amount 50000 --rate 0.12 --term 12 --purpose "input_purchase" --eligibility 0.85
    python -m services.analytics.digital_finance repay --loan-id UUID --amount 5000 --method mobile_money
    python -m services.analytics.digital_finance portfolio --location-id UUID
    python -m services.analytics.digital_finance premium --location-id UUID --product yield_guarantee --coverage 200000
    python -m services.analytics.digital_finance eligibility --location-id UUID --amount 75000
"""

import json
import uuid
from datetime import datetime, date, timedelta, timezone

from services.common.commands import CommandLine
from ..common.logging import get_logger

logger = get_logger("analytics.digital_finance")


# ============================================================
# Account Management
# ============================================================

def create_account(
    conn,
    location_id: str,
    account_type: str,
    currency: str = "KES",
    holder_name: str = None,
    provider: str = None,
    account_number: str = None,
    credit_limit: float = 0,
    metadata: dict = None,
) -> dict:
    """Create a financial account for a location."""
    cur = conn.cursor()
    account_id = str(uuid.uuid4())
    account_name = holder_name or f"{account_type} account"

    try:
        cur.execute(
            """
            INSERT INTO farm_financial_account
                (id, location_id, account_name, account_type, currency_code,
                 provider, account_number, credit_limit, metadata, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            RETURNING id, created_at
            """,
            (
                account_id, location_id, account_name, account_type, currency,
                provider, account_number, credit_limit,
                json.dumps(metadata or {}), holder_name,
            ),
        )
        row = cur.fetchone()
        conn.commit()

        return {
            "account_id": account_id,
            "location_id": location_id,
            "account_name": account_name,
            "account_type": account_type,
            "currency_code": currency,
            "balance": 0,
            "status": "active",
            "created_at": row[1].isoformat() if row and row[1] else None,
        }
    finally:
        cur.close()


# ============================================================
# Transaction Recording
# ============================================================

def record_transaction(
    conn,
    account_id: str,
    tx_type: str,
    amount: float,
    direction: str,
    currency: str = "KES",
    description: str = None,
    reference_id: str = None,
    reference_type: str = None,
    external_ref: str = None,
    fee_amount: float = 0,
    source_system: str = None,
    source_id: str = None,
    source_raw: dict = None,
    metadata: dict = None,
) -> dict:
    """Record a financial transaction and update account balance."""
    cur = conn.cursor()
    tx_id = str(uuid.uuid4())

    # Map direction labels to schema values
    dir_map = {"credit": "inflow", "debit": "outflow", "inflow": "inflow", "outflow": "outflow"}
    direction_schema = dir_map.get(direction, direction)

    try:
        # Get current account info
        cur.execute(
            "SELECT location_id, balance, currency_code FROM farm_financial_account WHERE id = %s",
            (account_id,),
        )
        acct = cur.fetchone()
        if not acct:
            raise ValueError(f"Account not found: {account_id}")
        location_id, current_balance, acct_currency = acct

        if currency == "KES" and acct_currency != "KES":
            currency = acct_currency

        # Insert transaction
        cur.execute(
            """
            INSERT INTO dfs_financial_transaction
                (id, account_id, location_id, transaction_type, amount,
                 currency_code, direction, reference_id, reference_type,
                 external_ref, fee_amount, source_system, source_id,
                 source_raw, metadata, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            RETURNING id, created_at
            """,
            (
                tx_id, account_id, location_id, tx_type, amount,
                currency, direction_schema, reference_id, reference_type,
                external_ref, fee_amount, source_system, source_id,
                json.dumps(source_raw) if source_raw else None,
                json.dumps(metadata or {}), description,
            ),
        )
        tx_row = cur.fetchone()

        # Update balance
        new_balance = current_balance + amount if direction_schema == "inflow" else current_balance - amount
        cur.execute(
            """
            UPDATE farm_financial_account
            SET balance = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (new_balance, account_id),
        )
        conn.commit()

        return {
            "transaction_id": tx_id,
            "account_id": account_id,
            "transaction_type": tx_type,
            "amount": amount,
            "currency_code": currency,
            "direction": direction_schema,
            "previous_balance": float(current_balance),
            "new_balance": float(new_balance),
            "status": "completed",
            "completed_at": tx_row[1].isoformat() if tx_row and tx_row[1] else None,
        }
    finally:
        cur.close()


# ============================================================
# Account Balance
# ============================================================

def get_account_balance(conn, account_id: str) -> dict:
    """Get current balance and recent transactions for an account."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, location_id, account_name, account_type, currency_code,
                   balance, available_credit, credit_limit, status, kyc_verified,
                   created_at
            FROM farm_financial_account
            WHERE id = %s
            """,
            (account_id,),
        )
        acct = cur.fetchone()
        if not acct:
            raise ValueError(f"Account not found: {account_id}")

        cols = [d[0] for d in cur.description]
        acct_row = dict(zip(cols, acct))

        # Recent transactions
        cur.execute(
            """
            SELECT id, transaction_type, amount, currency_code, direction,
                   status, completed_at, fee_amount
            FROM dfs_financial_transaction
            WHERE account_id = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (account_id,),
        )
        tx_cols = [d[0] for d in cur.description]
        recent_txs = [dict(zip(tx_cols, row)) for row in cur.fetchall()]

        # Summary stats
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_tx,
                COALESCE(SUM(CASE WHEN direction = 'inflow' THEN amount ELSE 0 END), 0) AS total_inflow,
                COALESCE(SUM(CASE WHEN direction = 'outflow' THEN amount ELSE 0 END), 0) AS total_outflow,
                MAX(completed_at) AS last_tx_at
            FROM dfs_financial_transaction
            WHERE account_id = %s AND status = 'completed'
            """,
            (account_id,),
        )
        stats_row = cur.fetchone()

        return {
            "account_id": account_id,
            "account_name": acct_row["account_name"],
            "account_type": acct_row["account_type"],
            "location_id": acct_row["location_id"],
            "currency_code": acct_row["currency_code"],
            "balance": float(acct_row["balance"]),
            "available_credit": float(acct_row["available_credit"]),
            "credit_limit": float(acct_row["credit_limit"]),
            "status": acct_row["status"],
            "kyc_verified": acct_row["kyc_verified"],
            "total_transactions": int(stats_row[0]) if stats_row[0] else 0,
            "total_inflow": float(stats_row[1]) if stats_row[1] else 0,
            "total_outflow": float(stats_row[2]) if stats_row[2] else 0,
            "last_transaction_at": stats_row[3].isoformat() if stats_row[3] else None,
            "recent_transactions": recent_txs,
        }
    finally:
        cur.close()


# ============================================================
# List Accounts
# ============================================================

def list_accounts(conn, location_id: str) -> dict:
    """List all financial accounts for a location."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT a.id, a.account_name, a.account_type, a.currency_code,
                   a.balance, a.available_credit, a.credit_limit, a.status,
                   a.kyc_verified, a.created_at,
                   (SELECT COUNT(*)
                    FROM dfs_financial_transaction t
                    WHERE t.account_id = a.id AND t.status = 'completed'
                   ) AS total_transactions
            FROM farm_financial_account a
            WHERE a.location_id = %s
            ORDER BY a.created_at DESC
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        accounts = []
        for row in cur.fetchall():
            acct = dict(zip(cols, row))
            acct["balance"] = float(acct["balance"])
            acct["available_credit"] = float(acct["available_credit"])
            acct["credit_limit"] = float(acct["credit_limit"])
            accounts.append(acct)

        total_balance = sum(a["balance"] for a in accounts)

        return {
            "location_id": location_id,
            "account_count": len(accounts),
            "total_balance": round(total_balance, 2),
            "accounts": accounts,
        }
    finally:
        cur.close()


# ============================================================
# Insurance Policy
# ============================================================

def create_insurance_policy(
    conn,
    location_id: str,
    product_type: str,
    coverage_amount: float,
    premium: float,
    risk_score: float = None,
    crop_type: str = None,
    area_hectares: float = None,
    coverage_start: str = None,
    coverage_end: str = None,
    deductible_pct: float = 0,
    account_id: str = None,
    metadata: dict = None,
) -> dict:
    """Create an insurance policy linked to CRISP scores."""
    cur = conn.cursor()
    policy_id = str(uuid.uuid4())
    policy_number = f"POL-{date.today().strftime('%Y%m%d')}-{policy_id[:8].upper()}"

    # Look up product_type_id
    cur.execute(
        "SELECT id, code, name FROM dfs_insurance_product_type WHERE code = %s",
        (product_type,),
    )
    pt_row = cur.fetchone()
    product_type_id = pt_row[0] if pt_row else None

    # Fetch CRISP composite if not provided
    risk_rating = None
    if risk_score is not None:
        risk_score_val = float(risk_score)
        risk_rating = _crisp_rating(risk_score_val)
    else:
        cur.execute(
            """
            SELECT overall_score FROM crisp_risk_assessment
            WHERE location_id = %s ORDER BY assessed_at DESC LIMIT 1
            """,
            (location_id,),
        )
        crisp_row = cur.fetchone()
        if crisp_row and crisp_row[0] is not None:
            risk_score_val = float(crisp_row[0])
            risk_rating = _crisp_rating(risk_score_val)
        else:
            risk_score_val = None

    start_date = date.fromisoformat(coverage_start) if coverage_start else date.today()
    end_date = date.fromisoformat(coverage_end) if coverage_end else start_date + timedelta(days=365)

    try:
        cur.execute(
            """
            INSERT INTO crop_insurance_policy
                (id, location_id, product_type_id, account_id,
                 policy_number, crop_type, area_hectares,
                 sum_insured, premium_amount, deductible_pct,
                 risk_score, risk_rating,
                 coverage_start, coverage_end,
                 status, metadata, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', %s::jsonb, 'system')
            RETURNING id, created_at
            """,
            (
                policy_id, location_id, product_type_id, account_id,
                policy_number, crop_type, area_hectares,
                coverage_amount, premium, deductible_pct,
                risk_score_val, risk_rating,
                start_date, end_date,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        return {
            "policy_id": policy_id,
            "location_id": location_id,
            "policy_number": policy_number,
            "product_type": product_type,
            "sum_insured": coverage_amount,
            "premium_amount": premium,
            "risk_score": risk_score_val,
            "risk_rating": risk_rating,
            "coverage_start": start_date.isoformat(),
            "coverage_end": end_date.isoformat(),
            "status": "draft",
            "created_at": row[1].isoformat() if row and row[1] else None,
        }
    finally:
        cur.close()


# ============================================================
# Insurance Claim
# ============================================================

def file_insurance_claim(
    conn,
    policy_id: str,
    claim_type: str,
    amount: float,
    trigger_event: str = None,
    evidence: dict = None,
    event_date: str = None,
    description: str = None,
    metadata: dict = None,
) -> dict:
    """File an insurance claim against a policy."""
    cur = conn.cursor()
    claim_id = str(uuid.uuid4())
    claim_number = f"CLM-{date.today().strftime('%Y%m%d')}-{claim_id[:8].upper()}"

    # Get policy details
    cur.execute(
        """
        SELECT p.location_id, p.sum_insured, p.risk_score, p.trigger_value,
               p.account_id
        FROM crop_insurance_policy p
        WHERE p.id = %s
        """,
        (policy_id,),
    )
    policy_row = cur.fetchone()
    if not policy_row:
        raise ValueError(f"Policy not found: {policy_id}")

    location_id = policy_row[0]
    sum_insured = float(policy_row[1]) if policy_row[1] else 0
    risk_score = float(policy_row[2]) if policy_row[2] else None
    trigger_value = float(policy_row[3]) if policy_row[3] else None
    account_id = policy_row[4]

    claim_amount = min(amount, sum_insured)
    claim_date = date.fromisoformat(event_date) if event_date else date.today()

    try:
        cur.execute(
            """
            INSERT INTO insurance_claim
                (id, policy_id, location_id, account_id,
                 claim_number, claim_date, event_date, event_type,
                 event_description, evidence_data,
                 claim_amount, status, metadata, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'filed', %s::jsonb, 'system')
            RETURNING id, created_at
            """,
            (
                claim_id, policy_id, location_id, account_id,
                claim_number, claim_date, claim_date,
                claim_type or trigger_event,
                description, json.dumps(evidence or {}),
                claim_amount, json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        return {
            "claim_id": claim_id,
            "policy_id": policy_id,
            "claim_number": claim_number,
            "location_id": location_id,
            "event_type": claim_type or trigger_event,
            "claim_amount": claim_amount,
            "status": "filed",
            "filed_at": row[1].isoformat() if row and row[1] else None,
        }
    finally:
        cur.close()


def evaluate_insurance_claim(
    conn,
    claim_id: str,
    status: str,
    adjustment: float = 0,
    notes: str = None,
    payout_amount: float = None,
) -> dict:
    """Approve, reject, or adjust an insurance claim."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, claim_amount, status FROM insurance_claim WHERE id = %s
            """,
            (claim_id,),
        )
        claim_row = cur.fetchone()
        if not claim_row:
            raise ValueError(f"Claim not found: {claim_id}")

        original_amount = float(claim_row[1])
        current_status = claim_row[2]

        if current_status not in ("filed", "under_review"):
            raise ValueError(f"Cannot evaluate claim in '{current_status}' status")

        final_payout = payout_amount if payout_amount is not None else max(original_amount - adjustment, 0)

        # Build update fields based on status
        ts_field = ""
        ts_value = ""
        payout_status = "pending"
        rejection_reason = None

        if status == "approved":
            ts_field = ", approved_at = NOW()"
            payout_status = "processing"
        elif status == "rejected":
            ts_field = ", rejected_at = NOW()"
            rejection_reason = notes
        elif status == "paid":
            ts_field = ", paid_at = NOW()"
            payout_status = "completed"

        cur.execute(
            f"""
            UPDATE insurance_claim
            SET status = %s,
                payout_amount = %s,
                payout_status = %s
                {ts_field},
                rejection_reason = COALESCE(%s, rejection_reason),
                metadata = metadata || %s::jsonb,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id
            """,
            (
                status, final_payout, payout_status,
                rejection_reason,
                json.dumps({"adjustment": adjustment, "notes": notes}),
                claim_id,
            ),
        )
        conn.commit()

        return {
            "claim_id": claim_id,
            "status": status,
            "original_amount": original_amount,
            "adjustment": adjustment,
            "payout_amount": final_payout,
            "notes": notes,
        }
    finally:
        cur.close()


# ============================================================
# Digital Lending
# ============================================================

def create_loan(
    conn,
    location_id: str,
    amount: float,
    interest_rate: float,
    term_months: int,
    purpose: str,
    eligibility_score: float = None,
    currency: str = "KES",
    account_id: str = None,
    loan_type: str = "working_capital",
    metadata: dict = None,
) -> dict:
    """Create a digital loan for a location."""
    cur = conn.cursor()
    loan_id = str(uuid.uuid4())
    loan_number = f"LN-{date.today().strftime('%Y%m%d')}-{loan_id[:8].upper()}"

    # Auto-determine loan_type from purpose if provided
    type_map = {
        "input_purchase": "input_advance",
        "equipment": "equipment",
        "emergency": "emergency",
        "expansion": "expansion",
        "working_capital": "working_capital",
        "post_harvest": "post_harvest",
    }
    if purpose in type_map:
        loan_type = type_map[purpose]

    disbursement_date = date.today()
    maturity_date = disbursement_date + timedelta(days=term_months * 30)
    disbursed_amount = amount
    status = "approved" if eligibility_score and eligibility_score >= 0.7 else "submitted"

    # Link to CRISP assessment
    crisp_id = None
    cur.execute(
        """
        SELECT id FROM crisp_risk_assessment
        WHERE location_id = %s ORDER BY assessed_at DESC LIMIT 1
        """,
        (location_id,),
    )
    crisp_row = cur.fetchone()
    if crisp_row:
        crisp_id = crisp_row[0]

    # Create repayment schedule
    monthly_payment = amount / term_months

    try:
        cur.execute(
            """
            INSERT INTO digital_lending
                (id, location_id, account_id, loan_number, loan_type,
                 principal, currency_code, interest_rate_pct, term_months,
                 disbursement_date, maturity_date,
                 eligibility_score, crisp_assessment_id,
                 disbursed_amount, disbursement_method,
                 status, disbursed, metadata, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s::jsonb, 'system')
            RETURNING id, created_at
            """,
            (
                loan_id, location_id, account_id, loan_number, loan_type,
                amount, currency, interest_rate * 100, term_months,
                disbursement_date, maturity_date,
                eligibility_score, crisp_id,
                disbursed_amount, "digital",
                status,
                json.dumps(metadata or {}),
            ),
        )
        loan_row = cur.fetchone()

        # Create installment schedule
        for i in range(1, term_months + 1):
            installment_id = str(uuid.uuid4())
            due = disbursement_date + timedelta(days=i * 30)
            interest_portion = amount * interest_rate / 12
            total_due = monthly_payment + interest_portion

            cur.execute(
                """
                INSERT INTO repayment_schedule
                    (id, loan_id, installment_no, principal_due, interest_due,
                     total_due, due_date, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                """,
                (
                    installment_id, loan_id, i,
                    round(monthly_payment, 4), round(interest_portion, 4),
                    round(total_due, 4), due,
                ),
            )

        conn.commit()

        return {
            "loan_id": loan_id,
            "location_id": location_id,
            "loan_number": loan_number,
            "loan_type": loan_type,
            "principal": amount,
            "currency_code": currency,
            "interest_rate_pct": round(interest_rate * 100, 4),
            "term_months": term_months,
            "monthly_payment": round(monthly_payment, 2),
            "total_interest": round(amount * interest_rate, 2),
            "total_repayable": round(amount + amount * interest_rate, 2),
            "disbursement_date": disbursement_date.isoformat(),
            "maturity_date": maturity_date.isoformat(),
            "eligibility_score": eligibility_score,
            "status": status,
            "created_at": loan_row[1].isoformat() if loan_row and loan_row[1] else None,
        }
    finally:
        cur.close()


# ============================================================
# Loan Repayment
# ============================================================

def record_repayment(
    conn,
    loan_id: str,
    amount: float,
    payment_method: str = "mobile_money",
    external_ref: str = None,
    metadata: dict = None,
) -> dict:
    """Record a loan repayment against the next pending installment."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, location_id, principal, interest_rate_pct, status,
                   account_id, currency_code
            FROM digital_lending WHERE id = %s
            """,
            (loan_id,),
        )
        loan_row = cur.fetchone()
        if not loan_row:
            raise ValueError(f"Loan not found: {loan_id}")

        location_id = loan_row[1]
        principal = float(loan_row[2])
        rate_pct = float(loan_row[3])
        loan_status = loan_row[4]
        account_id = loan_row[5]
        currency = loan_row[6]

        if loan_status not in ("approved", "disbursed", "repaying"):
            raise ValueError(f"Cannot repay loan in '{loan_status}' status")

        # Find next pending installment
        cur.execute(
            """
            SELECT id, installment_no, principal_due, interest_due, total_due,
                   total_paid, due_date
            FROM repayment_schedule
            WHERE loan_id = %s AND status IN ('pending', 'partial')
            ORDER BY installment_no ASC LIMIT 1
            """,
            (loan_id,),
        )
        sched_row = cur.fetchone()
        if not sched_row:
            raise ValueError("No pending installments for this loan")

        sched_id = sched_row[0]
        installment_no = sched_row[1]
        principal_due = float(sched_row[2])
        interest_due = float(sched_row[3])
        total_due = float(sched_row[4])
        already_paid = float(sched_row[5])
        remaining = total_due - already_paid
        payment = min(amount, remaining)
        new_paid = already_paid + payment

        # Update installment
        new_status = "paid" if new_paid >= total_due else "partial"
        cur.execute(
            """
            UPDATE repayment_schedule
            SET total_paid = %s, principal_paid = %s, interest_paid = %s,
                paid_date = CURRENT_DATE, status = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (new_paid, min(principal_due, new_paid), min(interest_due, max(new_paid - principal_due, 0)),
             new_status, sched_id),
        )

        # Record financial transaction
        tx_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO dfs_financial_transaction
                (id, account_id, location_id, transaction_type, amount,
                 currency_code, direction, reference_id, reference_type,
                 external_ref, status, source_system, metadata, created_by)
            VALUES (%s, %s, %s, 'loan_repayment', %s, %s, 'outflow', %s, 'loan', %s, 'completed', 'digital_finance', %s::jsonb, 'system')
            """,
            (
                tx_id, account_id, location_id, payment, currency,
                loan_id, external_ref,
                json.dumps({"loan_id": loan_id, "installment_no": installment_no, "payment_method": payment_method}),
                payment_method,
            ),
        )

        # Update loan status
        cur.execute(
            """
            UPDATE digital_lending
            SET status = 'repaying', updated_at = NOW()
            WHERE id = %s AND status = 'approved'
            """,
            (loan_id,),
        )

        # Check if fully repaid
        cur.execute(
            """
            SELECT COUNT(*), SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END)
            FROM repayment_schedule WHERE loan_id = %s
            """,
            (loan_id,),
        )
        count_row = cur.fetchone()
        total_inst = int(count_row[0]) if count_row[0] else 0
        paid_inst = int(count_row[1]) if count_row[1] else 0

        if total_inst > 0 and paid_inst == total_inst:
            cur.execute(
                """
                UPDATE digital_lending SET status = 'completed', closed_at = NOW(), updated_at = NOW()
                WHERE id = %s
                """,
                (loan_id,),
            )

        conn.commit()

        return {
            "loan_id": loan_id,
            "installment_no": installment_no,
            "payment_amount": payment,
            "method": payment_method,
            "installment_status": new_status,
            "total_paid_on_installment": round(new_paid, 2),
            "remaining_on_installment": round(max(remaining - payment, 0), 2),
            "loan_fully_repaid": paid_inst == total_inst and total_inst > 0,
        }
    finally:
        cur.close()


# ============================================================
# Portfolio Summary
# ============================================================

def get_portfolio_summary(conn, location_id: str) -> dict:
    """Aggregate financial summary for a location."""
    cur = conn.cursor()

    try:
        # Accounts
        cur.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(balance), 0),
                   COALESCE(SUM(available_credit), 0),
                   COALESCE(SUM(credit_limit), 0)
            FROM farm_financial_account
            WHERE location_id = %s AND status = 'active'
            """,
            (location_id,),
        )
        acct_row = cur.fetchone()
        account_count = int(acct_row[0]) if acct_row[0] else 0
        total_balance = float(acct_row[1]) if acct_row[1] else 0
        total_credit = float(acct_row[2]) if acct_row[2] else 0
        total_limit = float(acct_row[3]) if acct_row[3] else 0

        # Active loans
        cur.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(principal), 0),
                   COALESCE(SUM(penalty_accrued), 0)
            FROM digital_lending
            WHERE location_id = %s AND status IN ('approved', 'disbursed', 'repaying')
            """,
            (location_id,),
        )
        loan_row = cur.fetchone()
        active_loans = int(loan_row[0]) if loan_row[0] else 0
        total_loan_principal = float(loan_row[1]) if loan_row[1] else 0
        total_penalties = float(loan_row[2]) if loan_row[2] else 0

        # Repayment progress
        cur.execute(
            """
            SELECT COALESCE(SUM(total_paid), 0), COALESCE(SUM(total_due), 0)
            FROM repayment_schedule rs
            JOIN digital_lending dl ON dl.id = rs.loan_id
            WHERE dl.location_id = %s
            """,
            (location_id,),
        )
        repay_row = cur.fetchone()
        total_repaid = float(repay_row[0]) if repay_row[0] else 0
        total_due_all = float(repay_row[1]) if repay_row[1] else 0
        outstanding_balance = total_due_all - total_repaid

        # Insurance
        cur.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(sum_insured), 0),
                   COALESCE(SUM(premium_amount), 0)
            FROM crop_insurance_policy
            WHERE location_id = %s AND status IN ('issued', 'active')
            """,
            (location_id,),
        )
        ins_row = cur.fetchone()
        active_policies = int(ins_row[0]) if ins_row[0] else 0
        total_coverage = float(ins_row[1]) if ins_row[1] else 0
        total_premiums = float(ins_row[2]) if ins_row[2] else 0

        # Claims
        cur.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(claim_amount), 0),
                   COALESCE(SUM(CASE WHEN status = 'paid' THEN payout_amount ELSE 0 END), 0)
            FROM insurance_claim
            WHERE location_id = %s
            """,
            (location_id,),
        )
        claim_row = cur.fetchone()
        total_claims = int(claim_row[0]) if claim_row[0] else 0
        total_claim_amount = float(claim_row[1]) if claim_row[1] else 0
        total_payouts = float(claim_row[2]) if claim_row[2] else 0

        # Transaction activity (last 30 days)
        cur.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM dfs_financial_transaction
            WHERE location_id = %s
              AND completed_at >= NOW() - INTERVAL '30 days'
              AND status = 'completed'
            """,
            (location_id,),
        )
        tx_row = cur.fetchone()
        tx_30d_count = int(tx_row[0]) if tx_row[0] else 0
        tx_30d_volume = float(tx_row[1]) if tx_row[1] else 0

        return {
            "location_id": location_id,
            "accounts": {
                "count": account_count,
                "total_balance": round(total_balance, 2),
                "total_credit_used": round(total_credit, 2),
                "total_credit_limit": round(total_limit, 2),
            },
            "loans": {
                "active_count": active_loans,
                "total_principal": round(total_loan_principal, 2),
                "total_repaid": round(total_repaid, 2),
                "outstanding_balance": round(outstanding_balance, 2),
                "total_penalties": round(total_penalties, 2),
                "repayment_rate_pct": round(total_repaid / max(total_due_all, 1) * 100, 1),
            },
            "insurance": {
                "active_policies": active_policies,
                "total_coverage": round(total_coverage, 2),
                "total_premiums": round(total_premiums, 2),
                "total_claims": total_claims,
                "total_claim_amount": round(total_claim_amount, 2),
                "total_payouts": round(total_payouts, 2),
            },
            "activity_30d": {
                "transactions": tx_30d_count,
                "volume": round(tx_30d_volume, 2),
            },
        }
    finally:
        cur.close()


# ============================================================
# Insurance Premium Calculation
# ============================================================

def calculate_insurance_premium(
    conn,
    location_id: str,
    product_type: str,
    coverage_amount: float,
) -> dict:
    """Calculate risk-based insurance premium using CRISP scores."""
    cur = conn.cursor()

    try:
        # Fetch latest CRISP composite
        cur.execute(
            """
            SELECT overall_score, carbon_yield_score, climate_score,
                   policy_score, financial_score, implementation_score
            FROM crisp_risk_assessment
            WHERE location_id = %s ORDER BY assessed_at DESC LIMIT 1
            """,
            (location_id,),
        )
        crisp_row = cur.fetchone()

        if not crisp_row or crisp_row[0] is None:
            # Fallback: use default rate
            composite_score = 50.0
            dimension_scores = {}
        else:
            composite_score = float(crisp_row[0])
            dimension_scores = {
                "carbon_yield": float(crisp_row[1]) if crisp_row[1] else None,
                "climate": float(crisp_row[2]) if crisp_row[2] else None,
                "policy": float(crisp_row[3]) if crisp_row[3] else None,
                "financial": float(crisp_row[4]) if crisp_row[4] else None,
                "implementation": float(crisp_row[5]) if crisp_row[5] else None,
            }

        # Product-specific risk dimension mapping
        product_risk_dims = {
            "weather_index": ["climate"],
            "yield_guarantee": ["carbon_yield", "implementation"],
            "revenue_protection": ["financial", "carbon_yield", "climate"],
            "multi_peril": ["carbon_yield", "climate", "implementation", "policy"],
            "drought_cover": ["climate"],
            "flood_cover": ["climate"],
        }
        relevant_dims = product_risk_dims.get(product_type, ["carbon_yield", "climate"])

        # Base premium rate from CRISP score (0-100 scale where higher = more risk)
        # CRISP: 0 = low risk, 100 = high risk
        # Premium rate: 1% (low risk) to 8% (high risk)
        base_rate = 0.01 + (composite_score / 100.0) * 0.07

        # Adjust based on relevant dimensions
        relevant_scores = [
            v for k, v in dimension_scores.items()
            if k in relevant_dims and v is not None
        ]
        if relevant_scores:
            dim_avg = sum(relevant_scores) / len(relevant_scores)
            dim_adjustment = (dim_avg / 100.0) * 0.03 - 0.015
            base_rate += dim_adjustment

        # Clamp rate
        base_rate = max(0.01, min(base_rate, 0.10))

        premium = coverage_amount * base_rate
        risk_rating = _crisp_rating(composite_score)

        return {
            "location_id": location_id,
            "product_type": product_type,
            "coverage_amount": coverage_amount,
            "crisp_composite_score": round(composite_score, 2),
            "risk_rating": risk_rating,
            "relevant_risk_dimensions": relevant_dims,
            "dimension_scores": {k: round(v, 2) for k, v in dimension_scores.items() if v is not None},
            "base_premium_rate_pct": round(base_rate * 100, 2),
            "calculated_premium": round(premium, 2),
            "premium_to_coverage_ratio": round(premium / max(coverage_amount, 1) * 100, 2),
        }
    finally:
        cur.close()


# ============================================================
# Loan Eligibility Evaluation
# ============================================================

def evaluate_loan_eligibility(
    conn,
    location_id: str,
    requested_amount: float,
) -> dict:
    """Evaluate loan eligibility based on farm data and CRISP scores."""
    cur = conn.cursor()

    try:
        # CRISP scores
        cur.execute(
            """
            SELECT overall_score, financial_score, implementation_score
            FROM crisp_risk_assessment
            WHERE location_id = %s ORDER BY assessed_at DESC LIMIT 1
            """,
            (location_id,),
        )
        crisp_row = cur.fetchone()
        crisp_score = float(crisp_row[0]) if crisp_row and crisp_row[0] else 50.0
        financial_score = float(crisp_row[1]) if crisp_row and crisp_row[1] else 50.0
        impl_score = float(crisp_row[2]) if crisp_row and crisp_row[2] else 50.0

        # Revenue history
        cur.execute(
            """
            SELECT COALESCE(SUM(amount), 0), COUNT(*)
            FROM revenue_event
            WHERE location_id = %s
              AND event_date >= CURRENT_DATE - INTERVAL '12 months'
            """,
            (location_id,),
        )
        rev_row = cur.fetchone()
        annual_revenue = float(rev_row[0]) if rev_row[0] else 0
        revenue_count = int(rev_row[1]) if rev_row[1] else 0

        # Existing debt
        cur.execute(
            """
            SELECT COALESCE(SUM(principal), 0)
            FROM digital_lending
            WHERE location_id = %s AND status IN ('approved', 'disbursed', 'repaying')
            """,
            (location_id,),
        )
        debt_row = cur.fetchone()
        existing_debt = float(debt_row[0]) if debt_row[0] else 0

        # Yield data (for collateral estimation)
        cur.execute(
            """
            SELECT COALESCE(AVG(yield_amount), 0), COUNT(*)
            FROM harvest_yield_observation
            WHERE location_id = %s AND status IN ('verified', 'published')
            """,
            (location_id,),
        )
        yield_row = cur.fetchone()
        avg_yield = float(yield_row[0]) if yield_row[0] else 0
        yield_observations = int(yield_row[1]) if yield_row[1] else 0

        # Tree inventory (collateral proxy)
        cur.execute(
            """
            SELECT COALESCE(SUM(tree_count), 0)
            FROM tree_inventory
            WHERE location_id = %s
            """,
            (location_id,),
        )
        tree_row = cur.fetchone()
        tree_count = int(tree_row[0]) if tree_row[0] else 0

        # Compute eligibility score
        # Factor weights
        w_revenue = 0.30
        w_crisp = 0.25
        w_yield = 0.20
        w_debt_ratio = 0.15
        w_collateral = 0.10

        # Revenue factor (0-1)
        revenue_factor = min(annual_revenue / max(requested_amount, 1), 1.0) if annual_revenue > 0 else 0.2

        # CRISP factor (inverted: lower risk = higher score)
        crisp_factor = max(1.0 - (crisp_score / 100.0), 0.0)

        # Yield factor
        yield_factor = min(avg_yield / 2000.0, 1.0) if avg_yield > 0 else 0.3

        # Debt ratio factor
        debt_ratio = existing_debt / max(annual_revenue, 1)
        debt_factor = max(1.0 - debt_ratio, 0.0)

        # Collateral factor (tree-based)
        collateral_value = tree_count * 500  # KSh 500 per tree estimate
        collateral_factor = min(collateral_value / max(requested_amount, 1), 1.0)

        eligibility = (
            w_revenue * revenue_factor +
            w_crisp * crisp_factor +
            w_yield * yield_factor +
            w_debt_ratio * debt_factor +
            w_collateral * collateral_factor
        )
        eligibility = round(min(max(eligibility, 0), 1.0), 4)

        # Max eligible amount based on revenue multiple
        max_amount = annual_revenue * 0.5 if annual_revenue > 0 else requested_amount * eligibility

        # Decision
        if eligibility >= 0.7:
            decision = "approved"
            recommended_rate = 0.10 + (1.0 - eligibility) * 0.10
        elif eligibility >= 0.5:
            decision = "conditionally_approved"
            recommended_rate = 0.15 + (1.0 - eligibility) * 0.10
        else:
            decision = "requires_collateral"
            recommended_rate = 0.20 + (1.0 - eligibility) * 0.10

        return {
            "location_id": location_id,
            "requested_amount": requested_amount,
            "eligibility_score": eligibility,
            "decision": decision,
            "max_eligible_amount": round(max_amount, 2),
            "recommended_interest_rate_pct": round(recommended_rate * 100, 2),
            "factors": {
                "annual_revenue": round(annual_revenue, 2),
                "revenue_factor": round(revenue_factor, 4),
                "crisp_score": round(crisp_score, 2),
                "crisp_factor": round(crisp_factor, 4),
                "avg_yield_kg_ha": round(avg_yield, 2),
                "yield_factor": round(yield_factor, 4),
                "existing_debt": round(existing_debt, 2),
                "debt_ratio": round(debt_ratio, 4),
                "debt_factor": round(debt_factor, 4),
                "tree_count": tree_count,
                "estimated_collateral": round(collateral_value, 2),
                "collateral_factor": round(collateral_factor, 4),
            },
            "weights": {
                "revenue": w_revenue,
                "crisp": w_crisp,
                "yield": w_yield,
                "debt_ratio": w_debt_ratio,
                "collateral": w_collateral,
            },
        }
    finally:
        cur.close()


# ============================================================
# Helpers
# ============================================================

def _crisp_rating(score: float) -> str:
    """Map a higher-is-riskier CRISP score to a conventional rating."""
    if score is None:
        return "NR"
    if score < 20:
        return "AAA"
    if score < 44:
        return "AA"
    if score < 69:
        return "A"
    if score < 80:
        return "B"
    if score < 91:
        return "C"
    return "D"


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
