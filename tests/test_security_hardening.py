"""Regression tests for high-risk parser and evaluator boundaries."""

import pytest


def test_kml_import_uses_defusedxml() -> None:
    text = open("services/export/spatial_import.py").read()
    assert "defusedxml.ElementTree" in text


def test_strategy_xml_validation_uses_defusedxml() -> None:
    text = open("services/strategy_markup/validator.py").read()
    assert "from defusedxml import ElementTree as ET" in text


def test_stock_flow_rejects_code_execution() -> None:
    from services.systems.stock_flow import StockFlowSimulator

    simulator = StockFlowSimulator()
    assert simulator._safe_numeric_eval("2 * (3 + 4)") == 14
    with pytest.raises(ValueError):
        simulator._safe_numeric_eval("__import__('os').system('id')")
