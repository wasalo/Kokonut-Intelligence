"""Capital-accounting composite errors contain no raw source diagnostics."""

from services.capital import accounting_report

SECRET = "database password=private-token and confidential ledger row"


def test_each_capital_accounting_section_uses_bounded_failure_summary(monkeypatch):
    def fail(*_args):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(accounting_report, "assess_capacity", fail)
    monkeypatch.setattr(accounting_report, "compute_diversion_index", fail)
    monkeypatch.setattr(accounting_report, "capture_risk", fail)
    monkeypatch.setattr(accounting_report, "list_draft_credits", fail)

    result = accounting_report.build_capital_accounting(object(), "location-1")

    assert result["sections"] == {}
    assert result["errors"] == [
        "capacity failed (RuntimeError)",
        "diversion failed (RuntimeError)",
        "capture-risk analysis failed (RuntimeError)",
        "credit-ledger analysis failed (RuntimeError)",
    ]
    assert SECRET not in repr(result)
