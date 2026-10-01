"""Run browser-vault Web Crypto tests under Node's built-in test runner."""

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
NODE_TEST = ROOT / "tests" / "test_mobile_vault.mjs"


def test_browser_vault_crypto_storage_and_legacy_migration():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to exercise browser Web Crypto behavior")

    result = subprocess.run(
        [node, "--test", str(NODE_TEST)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
