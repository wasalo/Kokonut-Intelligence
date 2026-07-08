"""Financial Statement Formatter: Income Statement, Balance Sheet, Cash Flow Statement."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def generate_income_statement(conn, location_id: str) -> dict[str, Any]:
    """Generate an Income Statement (P&L) from existing financial data.

    Sections: Revenue, COGS, Gross Profit, Operating Expenses, NOI/Net Income.
    """
    cur = conn.cursor()

    # Revenue
    cur.execute(
        """
        SELECT COALESCE(SUM(amount_usd), 0) FROM revenue_event
        WHERE location_id = %s AND status IN ('verified', 'published')
        """,
        (location_id,),
    )
    revenue = float(cur.fetchone()[0] or 0)

    # Returns and discounts
    cur.execute(
        """
        SELECT COALESCE(SUM(return_amount + discount_amount), 0) FROM sales_event
        WHERE location_id = %s AND status IN ('verified', 'published')
        """,
        (location_id,),
    )
    returns = float(cur.fetchone()[0] or 0)

    # COGS (direct costs)
    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0) FROM expense_event
        WHERE location_id = %s AND status IN ('verified', 'published') AND is_direct = TRUE
        """,
        (location_id,),
    )
    cogs = float(cur.fetchone()[0] or 0)

    # Operating expenses (shared costs)
    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0) FROM expense_event
        WHERE location_id = %s AND status IN ('verified', 'published') AND is_direct = FALSE
        """,
        (location_id,),
    )
    opex = float(cur.fetchone()[0] or 0)

    # Location info
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.close()

    net_revenue = revenue - returns
    gross_profit = net_revenue - cogs
    net_income = gross_profit - opex
    operating_margin = (net_income / net_revenue * 100) if net_revenue > 0 else 0

    return {
        "report_type": "income_statement",
        "location_id": location_id,
        "location_name": location[0] if location else None,
        "revenue": {
            "gross_revenue_usd": round(revenue, 2),
            "returns_and_discounts_usd": round(returns, 2),
            "net_revenue_usd": round(net_revenue, 2),
        },
        "cost_of_goods_sold": {
            "cogs_usd": round(cogs, 2),
        },
        "gross_profit": {
            "gross_profit_usd": round(gross_profit, 2),
            "gross_margin_pct": round((gross_profit / net_revenue * 100) if net_revenue > 0 else 0, 2),
        },
        "operating_expenses": {
            "opex_usd": round(opex, 2),
        },
        "net_income": {
            "net_income_usd": round(net_income, 2),
            "operating_margin_pct": round(operating_margin, 2),
        },
        "limitations": [
            "Income statement is computed from governed verified/published data.",
            "Depreciation is not included (would require capex amortization schedules).",
            "Tax and interest are not tracked (no tax/interest expense records).",
            "Period is not filtered (shows all-time totals; period filtering requires additional parameters).",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_balance_sheet(conn, location_id: str) -> dict[str, Any]:
    """Generate a simplified Balance Sheet from existing financial data.

    Sections: Assets, Liabilities, Equity.
    Note: This is a simplified balance sheet suitable for smallholder/cooperative farms.
    Full GAAP balance sheet would require accounts_receivable, inventory, debt tables.
    """
    cur = conn.cursor()

    # Assets: treasury inflows (cash position)
    cur.execute(
        """
        SELECT COALESCE(SUM(usd_value), 0) FROM treasury_event
        WHERE location_id = %s AND flow_direction = 'inflow'
        """,
        (location_id,),
    )
    treasury_inflows = float(cur.fetchone()[0] or 0)

    # Assets: fixed assets from capex
    cur.execute(
        """
        SELECT COALESCE(SUM(amount_usd), 0) FROM expense_event
        WHERE location_id = %s AND status IN ('verified', 'published') AND is_capex = TRUE
        """,
        (location_id,),
    )
    fixed_assets = float(cur.fetchone()[0] or 0)

    # Liabilities: treasury outflows
    cur.execute(
        """
        SELECT COALESCE(SUM(usd_value), 0) FROM treasury_event
        WHERE location_id = %s AND flow_direction = 'outflow'
        """,
        (location_id,),
    )
    treasury_outflows = float(cur.fetchone()[0] or 0)

    # Equity: cumulative net income
    cur.execute(
        """
        SELECT COALESCE(SUM(amount_usd), 0) FROM revenue_event
        WHERE location_id = %s AND status IN ('verified', 'published')
        """,
        (location_id,),
    )
    total_revenue = float(cur.fetchone()[0] or 0)

    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0) FROM expense_event
        WHERE location_id = %s AND status IN ('verified', 'published')
        """,
        (location_id,),
    )
    total_expenses = float(cur.fetchone()[0] or 0)

    # Location info
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.close()

    total_assets = treasury_inflows + fixed_assets
    total_liabilities = treasury_outflows
    equity = total_revenue - total_expenses

    return {
        "report_type": "balance_sheet",
        "location_id": location_id,
        "location_name": location[0] if location else None,
        "assets": {
            "cash_and_investments_usd": round(treasury_inflows, 2),
            "fixed_assets_usd": round(fixed_assets, 2),
            "total_assets_usd": round(total_assets, 2),
        },
        "liabilities": {
            "total_liabilities_usd": round(total_liabilities, 2),
        },
        "equity": {
            "retained_earnings_usd": round(equity, 2),
        },
        "balance_check": {
            "total_usd": round(total_assets, 2),
            "balanced": abs(total_assets - total_liabilities - equity) < 0.01,
        },
        "limitations": [
            "Simplified balance sheet for smallholder/cooperative farm accounting.",
            "No accounts receivable, accounts payable, inventory, or debt tables exist.",
            "Fixed assets valued at historical cost, not current market value.",
            "Depreciation is not tracked (no amortization schedules).",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_cash_flow_statement(conn, location_id: str) -> dict[str, Any]:
    """Generate a Cash Flow Statement with Operating, Investing, and Financing sections."""
    cur = conn.cursor()

    # Operating: revenue - operating expenses
    cur.execute(
        """
        SELECT COALESCE(SUM(amount_usd), 0) FROM revenue_event
        WHERE location_id = %s AND status IN ('verified', 'published')
        """,
        (location_id,),
    )
    operating_revenue = float(cur.fetchone()[0] or 0)

    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0) FROM expense_event
        WHERE location_id = %s AND status IN ('verified', 'published')
        """,
        (location_id,),
    )
    operating_expenses = float(cur.fetchone()[0] or 0)

    # Investing: capex
    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0) FROM expense_event
        WHERE location_id = %s AND status IN ('verified', 'published') AND is_capex = TRUE
        """,
        (location_id,),
    )
    investing = float(cur.fetchone()[0] or 0)

    # Financing: treasury inflows (grants, loans)
    cur.execute(
        """
        SELECT COALESCE(SUM(usd_value), 0) FROM treasury_event
        WHERE location_id = %s AND flow_direction = 'inflow'
        """,
        (location_id,),
    )
    financing_inflows = float(cur.fetchone()[0] or 0)

    # Financing: treasury outflows (repayments)
    cur.execute(
        """
        SELECT COALESCE(SUM(usd_value), 0) FROM treasury_event
        WHERE location_id = %s AND flow_direction = 'outflow'
        """,
        (location_id,),
    )
    financing_outflows = float(cur.fetchone()[0] or 0)

    # Location info
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.close()

    operating_cf = operating_revenue - operating_expenses
    financing_cf = financing_inflows - financing_outflows
    net_cf = operating_cf - investing + financing_cf

    return {
        "report_type": "cash_flow_statement",
        "location_id": location_id,
        "location_name": location[0] if location else None,
        "operating_activities": {
            "revenue_usd": round(operating_revenue, 2),
            "expenses_usd": round(operating_expenses, 2),
            "net_operating_cf_usd": round(operating_cf, 2),
        },
        "investing_activities": {
            "capital_expenditures_usd": round(investing, 2),
            "net_investing_cf_usd": round(-investing, 2),
        },
        "financing_activities": {
            "inflows_usd": round(financing_inflows, 2),
            "outflows_usd": round(financing_outflows, 2),
            "net_financing_cf_usd": round(financing_cf, 2),
        },
        "net_cash_flow": {
            "net_cash_flow_usd": round(net_cf, 2),
        },
        "limitations": [
            "Cash flow statement computed from governed verified/published data.",
            "Operating activities include all revenue and expense events.",
            "Investing activities represent capital expenditures only.",
            "Financing activities represent treasury inflows and outflows.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
