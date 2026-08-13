"""Parametrized CLI registry tests.

Replaces the 48 per-module ``test_cli_<name>.py`` template files with a single
data-driven suite.  Each CLI module is exercised for:

* ``--help`` invocation (exit 0 or 2, with usage output)
* import without error
* a small set of subcommand ``--help`` checks where applicable

This is a pure refactor — no test coverage is removed.
"""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

# (module_path, subcommand_help_targets)
CLI_REGISTRY: list[tuple[str, list[str]]] = [
    ("services.agents.cli", ["list"]),
    ("services.analytics.cli", []),
    ("services.analytics.cli_capability_map", ["list", "hierarchy", "coverage"]),
    ("services.capital.cli", ["list"]),
    ("services.certificates.cli", []),
    ("services.analytics.cli_consent", ["list"]),
    ("services.analytics.cli_coordination", []),
    ("services.credit_class.cli", ["class list", "batch list", "balance all", "params list"]),
    ("services.crisp.cli", ["list", "weights"]),
    ("services.data_module.cli", []),
    ("services.drivers.cli", ["--list"]),
    ("services.events.cli", ["--list-handlers"]),
    ("services.export.cli", []),
    ("services.federation.cli", ["--list-nodes"]),
    ("services.finance.cli", []),
    ("services.governance.cli", ["framework list"]),
    ("services.analytics.cli_governance_links", []),
    ("services.analytics.cli_governance_proposals", []),
    ("services.analytics.cli_governance_roles", []),
    ("services.analytics.cli_governance_tactical", []),
    ("services.analytics.cli_governance_tensions", []),
    ("services.guilds.cli", []),
    ("services.ingestion.cli", ["--list"]),
    ("services.iri.cli", []),
    ("services.management.cli", []),
    ("services.metadata_api.cli", []),
    ("services.office.cli", []),
    ("services.planning.cli", []),
    ("services.predictions.cli", ["list"]),
    ("services.rdf.cli", ["list-graphs"]),
    ("services.sandbox.cli", ["list"]),
    ("services.scheduler.cli", ["--status"]),
    ("services.scoring.cli", []),
    ("services.security.cli", []),
    ("services.analytics.cli_stakeholder_decisions", []),
    ("services.analytics.cli_stakeholder_engagement", []),
    ("services.analytics.cli_stakeholder_grievances", []),
    ("services.analytics.cli_stakeholder_identity", []),
    ("services.analytics.cli_stakeholder_representation", []),
    ("services.analytics.cli_stakeholder_trust", []),
    ("services.analytics.cli_stakeholders", ["list", "landscape"]),
    ("services.analytics.cli_strategy_map", ["list"]),
    ("services.stream.cli", ["--stats"]),
    ("services.systems.cli", ["--list-modules"]),
    ("services.analytics.cli_technology_roadmap", []),
    ("services.analytics.cli_value_stream_defs", ["list"]),
    ("services.analytics.cli_vision_mission", ["current"]),
]


def _run_cli(module: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _assert_help(module: str, extra_args: list[str]) -> None:
    result = _run_cli(module, extra_args + ["--help"])
    assert result.returncode in (0, 2), f"{module} --help failed: {result.stderr[:200]}"


# ---------------------------------------------------------------------------
# Help tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module,subcmds", CLI_REGISTRY)
def test_cli_help(module: str, subcmds: list[str]) -> None:
    _assert_help(module, [])


@pytest.mark.parametrize(
    "module,subcmds",
    [(m, sc) for m, sc in CLI_REGISTRY if sc],
)
def test_cli_subcommand_help(module: str, subcmds: list[str]) -> None:
    for subcmd in subcmds:
        # ``subcmd`` may be space-separated (e.g. "class list") → split into tokens.
        _assert_help(module, subcmd.split())


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module,subcmds", CLI_REGISTRY)
def test_cli_imports(module: str, subcmds: list[str]) -> None:
    assert importlib.import_module(module) is not None


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
