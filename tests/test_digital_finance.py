#!/usr/bin/env python3
"""
Tests for Digital Finance
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import date, datetime, timezone

from services.analytics.digital_finance import (
    create_account,
    record_transaction,
    get_account_balance,
    list_accounts,
    create_insurance_policy,
    file_insurance_claim,
    evaluate_insurance_claim,
    create_loan,
    record_repayment,
    get_portfolio_summary,
    calculate_insurance_premium,
    evaluate_loan_eligibility,
    _crisp_rating,
)


class TestCreateAccount(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("acct-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_create_account_returns_account_id(self):
        result = create_account(
            self.conn, "loc-001", "savings", currency="KES", holder_name="John Doe",
        )
        self.assertIn("account_id", result)
        self.assertEqual(result["account_type"], "savings")
        self.assertEqual(result["currency_code"], "KES")
        self.assertEqual(result["balance"], 0)
        self.assertEqual(result["status"], "active")

    def test_create_account_calls_insert(self):
        create_account(self.conn, "loc-001", "savings")
        self.mock_cursor.execute.assert_called()
        self.conn.commit.assert_called_once()

    def test_create_account_with_defaults(self):
        result = create_account(self.conn, "loc-001", "savings")
        self.assertEqual(result["account_name"], "savings account")

    def test_create_account_closes_cursor(self):
        create_account(self.conn, "loc-001", "savings")
        self.mock_cursor.close.assert_called_once()


class TestRecordTransaction(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            ("loc-001", 5000.0, "KES"),
            ("tx-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]

    def test_record_transaction_updates_balance(self):
        result = record_transaction(
            self.conn, "acct-001", "deposit", 1000.0, "credit",
        )
        self.assertIn("transaction_id", result)
        self.assertEqual(result["amount"], 1000.0)
        self.assertEqual(result["previous_balance"], 5000.0)
        self.assertEqual(result["new_balance"], 6000.0)
        self.assertEqual(result["status"], "completed")

    def test_record_transaction_debit(self):
        self.mock_cursor.fetchone.side_effect = [
            ("loc-001", 5000.0, "KES"),
            ("tx-002", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        result = record_transaction(
            self.conn, "acct-001", "withdrawal", 2000.0, "debit",
        )
        self.assertEqual(result["new_balance"], 3000.0)
        self.assertEqual(result["direction"], "outflow")

    def test_record_transaction_not_found(self):
        self.mock_cursor.fetchone.side_effect = None
        self.mock_cursor.fetchone.return_value = None
        with self.assertRaises(ValueError):
            record_transaction(self.conn, "bad-id", "deposit", 100.0, "credit")

    def test_record_transaction_completes(self):
        record_transaction(self.conn, "acct-001", "deposit", 1000.0, "credit")
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestGetAccountBalance(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.description = [
            ("id",), ("location_id",), ("account_name",), ("account_type",),
            ("currency_code",), ("balance",), ("available_credit",),
            ("credit_limit",), ("status",), ("kyc_verified",), ("created_at",),
        ]
        self.mock_cursor.fetchone.side_effect = [
            ("acct-001", "loc-001", "Savings", "savings", "KES", 5000.0, 0.0, 0.0, "active", False, datetime(2026, 1, 1, tzinfo=timezone.utc)),
            (10, 15000.0, 3000.0, datetime(2026, 6, 1, tzinfo=timezone.utc)),
        ]
        self.mock_cursor.fetchall.return_value = []

    def test_get_account_balance_returns_balance(self):
        result = get_account_balance(self.conn, "acct-001")
        self.assertEqual(result["account_id"], "acct-001")
        self.assertEqual(result["balance"], 5000.0)
        self.assertEqual(result["total_transactions"], 10)

    def test_get_account_balance_not_found(self):
        self.mock_cursor.fetchone.side_effect = None
        self.mock_cursor.fetchone.return_value = None
        with self.assertRaises(ValueError):
            get_account_balance(self.conn, "bad-id")

    def test_get_account_balance_closes_cursor(self):
        get_account_balance(self.conn, "acct-001")
        self.mock_cursor.close.assert_called_once()


class TestListAccounts(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.description = [
            ("id",), ("account_name",), ("account_type",), ("currency_code",),
            ("balance",), ("available_credit",), ("credit_limit",),
            ("status",), ("kyc_verified",), ("created_at",), ("total_transactions",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("acct-001", "Savings", "savings", "KES", 5000.0, 0.0, 0.0, "active", False, datetime(2026, 1, 1, tzinfo=timezone.utc), 5),
            ("acct-002", "Credit", "credit", "KES", 1000.0, 2000.0, 5000.0, "active", True, datetime(2026, 2, 1, tzinfo=timezone.utc), 3),
        ]

    def test_list_accounts_returns_accounts_for_location(self):
        result = list_accounts(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["account_count"], 2)
        self.assertEqual(result["total_balance"], 6000.0)

    def test_list_accounts_empty(self):
        self.mock_cursor.fetchall.return_value = []
        result = list_accounts(self.conn, "loc-999")
        self.assertEqual(result["account_count"], 0)
        self.assertEqual(result["total_balance"], 0)


class TestCreateInsurancePolicy(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            ("pt-001", "weather_index", "Weather Index"),
            None,
            ("pol-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]

    def test_create_insurance_policy_creates_policy(self):
        result = create_insurance_policy(
            self.conn, "loc-001", "weather_index", 100000, 5000,
            risk_score=45.0, crop_type="maize",
        )
        self.assertIn("policy_id", result)
        self.assertEqual(result["sum_insured"], 100000)
        self.assertEqual(result["premium_amount"], 5000)
        self.assertEqual(result["status"], "draft")
        self.assertIn("POL-", result["policy_number"])

    def test_create_insurance_policy_completes(self):
        result = create_insurance_policy(
            self.conn, "loc-001", "weather_index", 100000, 5000,
        )
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()
        self.assertIn("policy_id", result)


class TestFileInsuranceClaim(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            ("loc-001", 100000.0, 45.0, 30.0, "acct-001"),
            ("clm-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]

    def test_file_insurance_claim_creates_claim(self):
        result = file_insurance_claim(
            self.conn, "pol-001", "drought", 20000,
            evidence={"rainfall_deficit": 40},
        )
        self.assertIn("claim_id", result)
        self.assertEqual(result["claim_amount"], 20000)
        self.assertEqual(result["status"], "filed")
        self.assertIn("CLM-", result["claim_number"])

    def test_file_insurance_claim_capped_at_sum_insured(self):
        self.mock_cursor.fetchone.side_effect = [
            ("loc-001", 100000.0, 45.0, 30.0, "acct-001"),
            ("clm-002", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        result = file_insurance_claim(self.conn, "pol-001", "drought", 200000)
        self.assertEqual(result["claim_amount"], 100000)

    def test_file_insurance_claim_not_found(self):
        self.mock_cursor.fetchone.side_effect = None
        self.mock_cursor.fetchone.return_value = None
        with self.assertRaises(ValueError):
            file_insurance_claim(self.conn, "bad-id", "drought", 20000)


class TestEvaluateInsuranceClaim(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            ("clm-001", 20000.0, "filed"),
            ("clm-001",),
        ]

    def test_evaluate_insurance_claim_updates_status(self):
        result = evaluate_insurance_claim(
            self.conn, "clm-001", "approved", adjustment=0,
        )
        self.assertEqual(result["claim_id"], "clm-001")
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["payout_amount"], 20000.0)

    def test_evaluate_insurance_claim_with_adjustment(self):
        self.mock_cursor.fetchone.side_effect = [
            ("clm-001", 20000.0, "filed"),
            ("clm-001",),
        ]
        result = evaluate_insurance_claim(
            self.conn, "clm-001", "approved", adjustment=5000,
        )
        self.assertEqual(result["payout_amount"], 15000.0)
        self.assertEqual(result["adjustment"], 5000)

    def test_evaluate_insurance_claim_not_found(self):
        self.mock_cursor.fetchone.side_effect = None
        self.mock_cursor.fetchone.return_value = None
        with self.assertRaises(ValueError):
            evaluate_insurance_claim(self.conn, "bad-id", "approved")


class TestCreateLoan(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            None,
            ("loan-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]

    def test_create_loan_creates_loan_and_schedule(self):
        result = create_loan(
            self.conn, "loc-001", 50000, 0.12, 12, "input_purchase",
            eligibility_score=0.85,
        )
        self.assertIn("loan_id", result)
        self.assertEqual(result["principal"], 50000)
        self.assertEqual(result["term_months"], 12)
        self.assertEqual(result["status"], "approved")
        self.assertIn("LN-", result["loan_number"])
        installments = [c for c in self.mock_cursor.execute.call_args_list
                        if "repayment_schedule" in str(c)]
        self.assertEqual(len(installments), 12)

    def test_create_loan_submitted_status(self):
        self.mock_cursor.fetchone.side_effect = [
            None,
            ("loan-002", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        result = create_loan(
            self.conn, "loc-001", 50000, 0.12, 12, "input_purchase",
            eligibility_score=0.5,
        )
        self.assertEqual(result["status"], "submitted")


class TestRecordRepayment(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            ("loan-001", "loc-001", 50000.0, 12.0, "approved", "acct-001", "KES"),
            ("sched-001", 1, 4166.67, 500.0, 4666.67, 0.0, date(2026, 2, 1)),
            (3, 0),
        ]

    def test_record_repayment_updates_installment(self):
        result = record_repayment(
            self.conn, "loan-001", 4666.67, payment_method="mobile_money",
        )
        self.assertEqual(result["loan_id"], "loan-001")
        self.assertEqual(result["installment_no"], 1)
        self.assertEqual(result["payment_amount"], 4666.67)
        self.assertEqual(result["installment_status"], "paid")
        self.assertFalse(result["loan_fully_repaid"])

    def test_record_repayment_partial(self):
        self.mock_cursor.fetchone.side_effect = [
            ("loan-001", "loc-001", 50000.0, 12.0, "approved", "acct-001", "KES"),
            ("sched-001", 1, 4166.67, 500.0, 4666.67, 0.0, date(2026, 2, 1)),
            (3, 0),
        ]
        result = record_repayment(self.conn, "loan-001", 2000.0)
        self.assertEqual(result["installment_status"], "partial")
        self.assertAlmostEqual(result["remaining_on_installment"], 2666.67, places=2)

    def test_record_repayment_not_found(self):
        self.mock_cursor.fetchone.side_effect = None
        self.mock_cursor.fetchone.return_value = None
        with self.assertRaises(ValueError):
            record_repayment(self.conn, "bad-id", 1000)


class TestGetPortfolioSummary(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            (2, 10000.0, 3000.0, 15000.0),
            (1, 50000.0, 0.0),
            (20000.0, 60000.0),
            (1, 100000.0, 5000.0),
            (2, 30000.0, 25000.0),
            (15, 75000.0),
        ]

    def test_get_portfolio_summary_aggregates_data(self):
        result = get_portfolio_summary(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["accounts"]["count"], 2)
        self.assertEqual(result["accounts"]["total_balance"], 10000.0)
        self.assertEqual(result["loans"]["active_count"], 1)
        self.assertEqual(result["loans"]["total_principal"], 50000.0)
        self.assertEqual(result["insurance"]["active_policies"], 1)
        self.assertEqual(result["insurance"]["total_claims"], 2)
        self.assertEqual(result["activity_30d"]["transactions"], 15)


class TestCalculateInsurancePremium(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_calculate_insurance_premium_returns_premium(self):
        self.mock_cursor.fetchone.return_value = (
            45.0, 40.0, 50.0, 30.0, 60.0, 55.0,
        )
        result = calculate_insurance_premium(
            self.conn, "loc-001", "weather_index", 100000,
        )
        self.assertIn("calculated_premium", result)
        self.assertGreater(result["calculated_premium"], 0)
        self.assertEqual(result["product_type"], "weather_index")
        self.assertEqual(result["coverage_amount"], 100000)

    def test_calculate_insurance_premium_no_crisp(self):
        self.mock_cursor.fetchone.return_value = None
        result = calculate_insurance_premium(
            self.conn, "loc-001", "weather_index", 100000,
        )
        self.assertIn("calculated_premium", result)
        self.assertEqual(result["crisp_composite_score"], 50.0)


class TestEvaluateLoanEligibility(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            (35.0, 40.0, 55.0),
            (120000.0, 12),
            (0.0,),
            (2500.0, 5),
            (200,),
        ]

    def test_evaluate_loan_eligibility_returns_score(self):
        result = evaluate_loan_eligibility(
            self.conn, "loc-001", 75000,
        )
        self.assertIn("eligibility_score", result)
        self.assertIn("decision", result)
        self.assertGreater(result["eligibility_score"], 0)
        self.assertEqual(result["requested_amount"], 75000)

    def test_evaluate_loan_eligibility_factors(self):
        result = evaluate_loan_eligibility(
            self.conn, "loc-001", 75000,
        )
        self.assertIn("factors", result)
        self.assertIn("weights", result)
        self.assertEqual(result["factors"]["annual_revenue"], 120000.0)


class TestCrispRating(unittest.TestCase):

    def test_rating_d(self):
        self.assertEqual(_crisp_rating(15), "D")

    def test_rating_c(self):
        self.assertEqual(_crisp_rating(30), "C")

    def test_rating_b(self):
        self.assertEqual(_crisp_rating(60), "B")

    def test_rating_a(self):
        self.assertEqual(_crisp_rating(75), "A")

    def test_rating_aa(self):
        self.assertEqual(_crisp_rating(85), "AA")

    def test_rating_aaa(self):
        self.assertEqual(_crisp_rating(95), "AAA")

    def test_rating_none(self):
        self.assertEqual(_crisp_rating(None), "NR")


if __name__ == "__main__":
    unittest.main()
