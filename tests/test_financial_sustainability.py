#!/usr/bin/env python3
"""
Tests for Financial Sustainability Calculator
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import date

from services.analytics.financial_sustainability import (
    compute_break_even_month,
    compute_revenue_sustainability_index,
    compute_cost_efficiency_ratio,
    compute_cash_flow_projection,
    classify_sustainability_status,
    _month_key,
)


def _rev(d, amt, rtype="sale"):
    return {"revenue_date": d, "revenue_type": rtype, "amount": amt, "amount_usd": amt, "currency": "USD", "payment_status": "paid"}


def _exp(d, amt, category="seeds", is_capex=False):
    return {"expense_date": d, "category": category, "amount": amt, "currency": "USD", "is_capex": is_capex}


class TestBreakEvenMonth(unittest.TestCase):

    def test_no_data(self):
        self.assertIsNone(compute_break_even_month([], []))

    def test_no_revenue(self):
        self.assertIsNone(compute_break_even_month([], [_exp(date(2026, 1, 1), 1000)]))

    def test_no_expense(self):
        self.assertIsNone(compute_break_even_month([_rev(date(2026, 1, 1), 1000)], []))

    def test_break_even_month_1(self):
        revs = [_rev(date(2026, 1, 15), 5000)]
        exps = [_exp(date(2026, 1, 5), 3000)]
        self.assertEqual(compute_break_even_month(revs, exps), 1)

    def test_break_even_month_3(self):
        revs = [
            _rev(date(2026, 1, 15), 1000),
            _rev(date(2026, 2, 15), 1000),
            _rev(date(2026, 3, 15), 2000),
        ]
        exps = [
            _exp(date(2026, 1, 5), 2000),
            _exp(date(2026, 2, 5), 1000),
            _exp(date(2026, 3, 5), 500),
        ]
        # Month 1: rev=1000, exp=2000 -> cum rev=1000, cum exp=2000 (no)
        # Month 2: rev=1000, exp=1000 -> cum rev=2000, cum exp=3000 (no)
        # Month 3: rev=2000, exp=500  -> cum rev=4000, cum exp=3500 (yes)
        self.assertEqual(compute_break_even_month(revs, exps), 3)

    def test_never_breaks_even(self):
        revs = [_rev(date(2026, 1, 15), 100), _rev(date(2026, 2, 15), 100)]
        exps = [_exp(date(2026, 1, 5), 500), _exp(date(2026, 2, 5), 500)]
        self.assertIsNone(compute_break_even_month(revs, exps))

    def test_multi_rev_per_month(self):
        revs = [
            _rev(date(2026, 1, 5), 1000),
            _rev(date(2026, 1, 20), 1500),
        ]
        exps = [_exp(date(2026, 1, 10), 2000)]
        # Month 1: rev=2500, exp=2000 -> break even at month 1
        self.assertEqual(compute_break_even_month(revs, exps), 1)


class TestRevenueSustainabilityIndex(unittest.TestCase):

    def test_insufficient_data(self):
        result = compute_revenue_sustainability_index([])
        self.assertEqual(result["trend"], "insufficient_data")
        self.assertEqual(result["sustainability_index"], 50.0)

    def test_single_point(self):
        result = compute_revenue_sustainability_index([_rev(date(2026, 1, 1), 1000)])
        self.assertEqual(result["trend"], "insufficient_data")
        self.assertEqual(result["data_points"], 1)

    def test_growing_revenue(self):
        revs = [
            _rev(date(2026, 1, 1), 1000),
            _rev(date(2026, 2, 1), 1500),
            _rev(date(2026, 3, 1), 2000),
            _rev(date(2026, 4, 1), 2500),
        ]
        result = compute_revenue_sustainability_index(revs)
        self.assertEqual(result["trend"], "growing")
        self.assertGreater(result["sustainability_index"], 50.0)
        self.assertGreater(result["slope_per_month"], 0)

    def test_declining_revenue(self):
        revs = [
            _rev(date(2026, 1, 1), 5000),
            _rev(date(2026, 2, 1), 4000),
            _rev(date(2026, 3, 1), 3000),
            _rev(date(2026, 4, 1), 2000),
        ]
        result = compute_revenue_sustainability_index(revs)
        self.assertEqual(result["trend"], "declining")
        self.assertLess(result["sustainability_index"], 50.0)

    def test_stable_revenue(self):
        revs = [
            _rev(date(2026, 1, 1), 1000),
            _rev(date(2026, 2, 1), 1001),
            _rev(date(2026, 3, 1), 999),
            _rev(date(2026, 4, 1), 1000),
        ]
        result = compute_revenue_sustainability_index(revs)
        self.assertEqual(result["trend"], "stable")


class TestCostEfficiencyRatio(unittest.TestCase):

    def test_no_data(self):
        result = compute_cost_efficiency_ratio([], [])
        self.assertIsNone(result["efficiency_ratio"])
        self.assertEqual(result["assessment"], "no_data")

    def test_efficient(self):
        revs = [_rev(date(2026, 1, 1), 10000)]
        exps = [_exp(date(2026, 1, 1), 5000)]
        result = compute_cost_efficiency_ratio(revs, exps)
        self.assertAlmostEqual(result["efficiency_ratio"], 2.0)
        self.assertEqual(result["assessment"], "highly_efficient")

    def test_break_even_ratio(self):
        revs = [_rev(date(2026, 1, 1), 5000)]
        exps = [_exp(date(2026, 1, 1), 5000)]
        result = compute_cost_efficiency_ratio(revs, exps)
        self.assertAlmostEqual(result["efficiency_ratio"], 1.0)
        self.assertEqual(result["assessment"], "break_even")

    def test_inefficient(self):
        revs = [_rev(date(2026, 1, 1), 1000)]
        exps = [_exp(date(2026, 1, 1), 5000)]
        result = compute_cost_efficiency_ratio(revs, exps)
        self.assertAlmostEqual(result["efficiency_ratio"], 0.2)
        self.assertEqual(result["assessment"], "inefficient")

    def test_capex_excluded_from_opex(self):
        revs = [_rev(date(2026, 1, 1), 10000)]
        exps = [
            _exp(date(2026, 1, 1), 3000, category="seeds", is_capex=False),
            _exp(date(2026, 1, 1), 7000, category="equipment", is_capex=True),
        ]
        result = compute_cost_efficiency_ratio(revs, exps)
        # Total exp = 10000, OpEx = 3000
        self.assertAlmostEqual(result["efficiency_ratio"], 1.0)
        self.assertAlmostEqual(result["operating_ratio"], 10000 / 3000, places=2)

    def test_category_breakdown(self):
        revs = [_rev(date(2026, 1, 1), 10000)]
        exps = [
            _exp(date(2026, 1, 1), 2000, category="seeds"),
            _exp(date(2026, 1, 1), 3000, category="labor"),
        ]
        result = compute_cost_efficiency_ratio(revs, exps)
        self.assertIn("seeds", result["cost_categories"])
        self.assertIn("labor", result["cost_categories"])
        self.assertEqual(result["cost_categories"]["seeds"], 2000)
        self.assertEqual(result["cost_categories"]["labor"], 3000)


class TestCashFlowProjection(unittest.TestCase):

    def test_no_data(self):
        result = compute_cash_flow_projection([], [])
        self.assertEqual(result["avg_monthly_revenue"], 0)
        self.assertEqual(result["projected_runway_months"], None)
        self.assertEqual(len(result["projections"]), 0)

    def test_basic_projection(self):
        revs = [
            _rev(date(2026, 1, 1), 1000),
            _rev(date(2026, 2, 1), 1000),
            _rev(date(2026, 3, 1), 1000),
        ]
        exps = [
            _exp(date(2026, 1, 1), 800),
            _exp(date(2026, 2, 1), 800),
            _exp(date(2026, 3, 1), 800),
        ]
        result = compute_cash_flow_projection(revs, exps, months_ahead=3)
        self.assertEqual(result["avg_monthly_revenue"], 1000)
        self.assertEqual(result["avg_monthly_expenses"], 800)
        self.assertEqual(result["avg_monthly_net"], 200)
        self.assertIsNone(result["projected_runway_months"])
        self.assertEqual(len(result["projections"]), 3)
        self.assertEqual(result["projections"][0]["projected_net"], 200)

    def test_negative_cash_flow(self):
        revs = [
            _rev(date(2026, 1, 1), 500),
            _rev(date(2026, 2, 1), 500),
        ]
        exps = [
            _exp(date(2026, 1, 1), 1000),
            _exp(date(2026, 2, 1), 1000),
        ]
        result = compute_cash_flow_projection(revs, exps, months_ahead=3)
        self.assertEqual(result["avg_monthly_net"], -500)
        # current_position = 1000 - 2000 = -1000
        # runway = 0 since position is negative
        self.assertEqual(result["projected_runway_months"], 0.0)

    def test_runway_calculation(self):
        revs = [
            _rev(date(2026, 1, 1), 500),
            _rev(date(2026, 2, 1), 500),
            _rev(date(2026, 3, 1), 500),
        ]
        exps = [
            _exp(date(2026, 1, 1), 600),
            _exp(date(2026, 2, 1), 600),
            _exp(date(2026, 3, 1), 600),
        ]
        result = compute_cash_flow_projection(revs, exps, months_ahead=3)
        # cumulative: rev=1500, exp=1800, position=-300, avg_net=-100
        self.assertEqual(result["projected_runway_months"], 0.0)

    def test_projection_months(self):
        revs = [_rev(date(2026, 1, 1), 1000)]
        exps = [_exp(date(2026, 1, 1), 500)]
        result = compute_cash_flow_projection(revs, exps, months_ahead=6)
        self.assertEqual(len(result["projections"]), 6)


class TestClassifySustainabilityStatus(unittest.TestCase):

    def test_no_data(self):
        self.assertEqual(classify_sustainability_status(None, None, 50.0), "draft")

    def test_self_sustaining(self):
        self.assertEqual(classify_sustainability_status(3, 1.8, 70.0), "self_sustaining")

    def test_transitioning(self):
        self.assertEqual(classify_sustainability_status(6, 1.2, 55.0), "transitioning")

    def test_grant_dependent(self):
        self.assertEqual(classify_sustainability_status(12, 0.9, 40.0), "grant_dependent")

    def test_needs_rework(self):
        self.assertEqual(classify_sustainability_status(None, 0.3, 20.0), "needs_rework")

    def test_draft_on_none_ratio(self):
        self.assertEqual(classify_sustainability_status(5, None, 50.0), "draft")


class TestMonthKey(unittest.TestCase):

    def test_date_object(self):
        self.assertEqual(_month_key(date(2026, 3, 15)), "2026-03")

    def test_string(self):
        self.assertEqual(_month_key("2026-03-15"), "2026-03")


if __name__ == "__main__":
    unittest.main()
