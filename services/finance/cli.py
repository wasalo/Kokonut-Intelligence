#!/usr/bin/env python3
"""Finance CLI: Financial statements and investment analysis.

Usage:
    python3 -m services.finance --income-statement --location-id UUID
    python3 -m services.finance --balance-sheet --location-id UUID
    python3 -m services.finance --cash-flow-statement --location-id UUID
    python3 -m services.finance --investment-analysis --location-id UUID
    python3 -m services.finance --list
"""

import argparse
import json

from .financial_statements import (
    generate_balance_sheet,
    generate_cash_flow_statement,
    generate_income_statement,
)
from .return_calculator import compute_investment_analysis


def get_pg():
    import psycopg2
    from ..common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )


def main():
    parser = argparse.ArgumentParser(description="Finance CLI: Financial statements and investment analysis")
    parser.add_argument("--income-statement", action="store_true", help="Generate Income Statement")
    parser.add_argument("--balance-sheet", action="store_true", help="Generate Balance Sheet")
    parser.add_argument("--cash-flow-statement", action="store_true", help="Generate Cash Flow Statement")
    parser.add_argument("--investment-analysis", action="store_true", help="Compute IRR, NPV, MIRR, payback")
    parser.add_argument("--location-id", help="Location UUID")
    parser.add_argument("--list", action="store_true", help="List available report types")
    args = parser.parse_args()

    if not any([args.income_statement, args.balance_sheet, args.cash_flow_statement, args.investment_analysis, args.list]):
        parser.error("Specify a report type: --income-statement, --balance-sheet, --cash-flow-statement, --investment-analysis, or --list")

    if args.list:
        print("Available finance reports:")
        print("  --income-statement      Income Statement (P&L)")
        print("  --balance-sheet         Balance Sheet (simplified)")
        print("  --cash-flow-statement   Cash Flow Statement")
        print("  --investment-analysis   IRR, NPV, MIRR, payback, ROI")
        return

    if not args.location_id:
        parser.error("--location-id is required")

    conn = get_pg()

    if args.income_statement:
        result = generate_income_statement(conn, args.location_id)
    elif args.balance_sheet:
        result = generate_balance_sheet(conn, args.location_id)
    elif args.cash_flow_statement:
        result = generate_cash_flow_statement(conn, args.location_id)
    elif args.investment_analysis:
        result = compute_investment_analysis(conn, args.location_id)
    else:
        parser.error("Unknown report type")

    conn.close()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
