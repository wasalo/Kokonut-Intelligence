"""Keep documented Python service commands aligned with module entry points."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (
    ROOT / "AGENTS.md",
    ROOT / "docs" / "gateway.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "api-reference.md",
)
COMMAND_RE = re.compile(r"python3 -m (services\.[A-Za-z0-9_\.]+)")


def _is_runnable_module(module_name: str) -> bool:
    module_path = ROOT.joinpath(*module_name.split("."))
    if module_path.with_suffix(".py").is_file():
        return True
    return (module_path / "__main__.py").is_file()


def test_documented_service_commands_have_entry_points():
    commands = {
        command
        for document in DOCUMENTS
        for command in COMMAND_RE.findall(document.read_text())
    }
    missing = sorted(command for command in commands if not _is_runnable_module(command))
    assert not missing, "Documented service modules are not runnable with python -m: " + ", ".join(missing)


def test_is_runnable_module_detects_py_files(tmp_path):
    mod_dir = tmp_path / "services" / "test_mod"
    mod_dir.mkdir(parents=True)
    (mod_dir / "__init__.py").write_text("")
    assert _is_runnable_module("services.test_mod")


def test_is_runnable_module_detects_main_py(tmp_path):
    mod_dir = tmp_path / "services" / "test_pkg"
    mod_dir.mkdir(parents=True)
    (mod_dir / "__main__.py").write_text("")
    assert _is_runnable_module("services.test_pkg")


def test_is_runnable_module_rejects_missing(tmp_path):
    assert not _is_runnable_module("services.nonexistent_module")
