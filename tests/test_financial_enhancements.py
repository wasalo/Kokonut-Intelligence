"""Financial enhancements tests: statements, IRR/NPV, investment analysis."""

from pathlib import Path

from services.finance.financial_statements import (
    generate_balance_sheet,
    generate_cash_flow_statement,
    generate_income_statement,
)
from services.finance.return_calculator import (
    compute_irr,
    compute_investment_analysis,
    compute_mirr,
    compute_npv,
    compute_payback_period,
    compute_roi,
)

SCHEMA = Path("schemas/postgres/070_financial_enhancement.sql")


# ---------------------------------------------------------------------------
# IRR/NPV unit tests (no database)
# ---------------------------------------------------------------------------

def test_irr_converges() -> None:
    cash_flows = [-50000, 12000, 15000, 18000, 20000]
    irr = compute_irr(cash_flows)
    assert irr is not None
    assert 0.0 < irr < 1.0  # Should be positive and reasonable


def test_irr_no_convergence() -> None:
    # Edge case: no initial investment — IRR is undefined
    irr = compute_irr([0, 1000, 2000])
    assert irr is None


def test_irr_insufficient_data() -> None:
    irr = compute_irr([])
    assert irr is None


def test_npv_positive() -> None:
    # Higher cash flows should yield positive NPV
    npv = compute_npv([-50000, 20000, 20000, 20000, 20000], 0.08)
    assert npv > 0  # Should be positive NPV


def test_npv_negative() -> None:
    npv = compute_npv([-50000, 5000, 5000, 5000], 0.08)
    assert npv < 0  # Should be negative NPV


def test_mirr_converges() -> None:
    cash_flows = [-50000, 12000, 15000, 18000, 20000]
    mirr = compute_mirr(cash_flows)
    assert mirr is not None
    assert mirr > 0


def test_payback_period() -> None:
    payback = compute_payback_period([-50000, 20000, 20000, 20000])
    assert payback is not None
    assert 2.0 <= payback <= 3.0  # Should recover in ~2.5 years


def test_payback_never_recovered() -> None:
    payback = compute_payback_period([-50000, 10000, 10000])
    assert payback is None  # Never fully recovered


def test_roi() -> None:
    roi = compute_roi([-50000, 20000, 20000, 20000])
    # total_return = 60000, initial = 50000, roi = (60000/50000)*100 = 120%
    assert roi == 120.0


# ---------------------------------------------------------------------------
# Financial statement tests (mock data)
# ---------------------------------------------------------------------------

class _MockCursor:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single

    def execute(self, query, params=None):
        pass

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._single

    def close(self):
        pass


class _MockConn:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single

    def cursor(self, cursor_factory=None):
        return _MockCursor(self._rows, self._single)


def test_income_statement_empty() -> None:
    class _IncomeConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                # Query order: revenue, returns, cogs, opex, location name
                if self._calls == 5:
                    c._single = ("Test Farm",)  # location name
                else:
                    c._single = (0,)  # all financial queries return 0
            c.execute = execute
            return c

    result = generate_income_statement(_IncomeConn(), "test-location")
    assert result["report_type"] == "income_statement"
    assert result["revenue"]["gross_revenue_usd"] == 0
    assert result["net_income"]["net_income_usd"] == 0


def test_balance_sheet_empty() -> None:
    class _BSConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                c._single = (0,)  # all financial queries return 0
            c.execute = execute
            return c

    result = generate_balance_sheet(_BSConn(), "test-location")
    assert result["report_type"] == "balance_sheet"
    assert result["assets"]["total_assets_usd"] == 0
    assert result["equity"]["retained_earnings_usd"] == 0


def test_cash_flow_statement_empty() -> None:
    class _CFConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                c._single = (0,)  # all financial queries return 0
            c.execute = execute
            return c

    result = generate_cash_flow_statement(_CFConn(), "test-location")
    assert result["report_type"] == "cash_flow_statement"
    assert result["net_cash_flow"]["net_cash_flow_usd"] == 0


def test_investment_analysis_insufficient_data() -> None:
    result = compute_investment_analysis(_MockConn(rows=[], single=None), "test-location")
    assert result["status"] == "insufficient_data"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_irr_converges()
    test_irr_no_convergence()
    test_irr_insufficient_data()
    test_npv_positive()
    test_npv_negative()
    test_mirr_converges()
    test_payback_period()
    test_payback_never_recovered()
    test_roi()
    test_income_statement_empty()
    test_balance_sheet_empty()
    test_cash_flow_statement_empty()
    test_investment_analysis_insufficient_data()
    print("All tests passed.")
