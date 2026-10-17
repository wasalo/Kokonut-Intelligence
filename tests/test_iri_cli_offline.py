"""Linked-data CLI help stays available without loading encrypted settings."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("module", "arguments", "expected_option"),
    [
        (
            "services.iri.cli",
            ["generate", "--help"],
            "--publish-public-location",
        ),
        (
            "services.metadata_api.cli",
            ["serve", "--help"],
            "--port",
        ),
    ],
)
def test_linked_data_cli_help_does_not_load_sops_or_open_database(
    module,
    arguments,
    expected_option,
):
    environment = os.environ.copy()
    environment.pop("KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT", None)

    result = subprocess.run(
        [sys.executable, "-m", module, *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert expected_option in result.stdout
    assert "SOPS" not in result.stderr
