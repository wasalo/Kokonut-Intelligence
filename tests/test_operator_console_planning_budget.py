"""Console contract for read-only CAP-031 location budget summaries."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


def _function(source: str, declaration: str, next_declaration: str) -> str:
    start = source.index(declaration)
    end = source.index(next_declaration, start)
    return source[start:end]


def test_budget_panel_requires_exact_location_read_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="planning-budget-summary".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert "Amounts remain in each plan’s currency" in panel.group()
    assert 'scope.resource === "planning_budget" && scope.action === "read"' in source
    assert "planningBudgetLocations = new Set(planningBudgetLocationIds)" in source
    assert "planningBudgetSummary.hidden = false" in source


def test_budget_reader_uses_protected_no_store_route_stale_guards_and_bounded_pages():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadPlanningBudgetSummaries(", "async function loadSession()")
    assert '`/operator/api/planning/${encodeURIComponent(locationId)}/budgets?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "planningBudgetLocations.has(locationId)" in reader
    assert "requestVersion !== planningBudgetRequestVersion" in reader
    assert "locationId !== planningBudgetLocation.value" in reader
    assert "nextOffset <= 10000" in reader
    assert "innerHTML" not in reader


def test_budget_table_uses_fixed_summary_fields_and_keeps_native_currency():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadPlanningBudgetSummaries(", "async function loadSession()")
    for field in (
        "plan_status", "currency", "period_start", "period_end", "has_objective",
        "budget_line_count", "planned_amount", "verified_expense_amount",
        "budget_variance", "nonmatching_currency_expense_count", "planning_scenario_count",
    ):
        assert f"plan.{field}" in reader
    assert "String(value)} ${currency}" in reader
    assert "textContent" in reader
    assert "innerHTML" not in reader
    for private_field in (
        "financial_plan_id", "plan_name", "objective_id", "category", "assumption",
        "expense_description", "vendor", "evidence", "transaction_id",
    ):
        assert f"plan.{private_field}" not in reader


def test_refresh_location_and_pagination_controls_are_wired_with_unique_ids():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'planningBudgetLocation.addEventListener("change", () => loadPlanningBudgetSummaries())' in source
    assert 'document.querySelector("#planning-budget-refresh").addEventListener("click", () => loadPlanningBudgetSummaries())' in source
    assert 'planningBudgetMore.addEventListener("click", () => loadPlanningBudgetSummaries(true))' in source
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"


def test_inline_javascript_parses_when_node_is_available():
    node = shutil.which("node")
    if node is None:
        return
    source = CONSOLE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", source, re.DOTALL)
    assert len(scripts) == 1
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", encoding="utf-8") as script:
        script.write(scripts[0])
        script.flush()
        result = subprocess.run(
            [node, "--check", script.name],
            check=False,
            capture_output=True,
            text=True,
        )
    assert result.returncode == 0, result.stderr
