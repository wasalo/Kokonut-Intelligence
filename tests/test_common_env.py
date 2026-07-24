"""Tests for strict encrypted/plaintext environment loading policy."""

import subprocess

import pytest

from services.common import env


def _reset_loader(monkeypatch, tmp_path):
    monkeypatch.setattr(env, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(env, "_LOADED", False)
    monkeypatch.delenv("KOKONUT_ALLOW_PLAINTEXT_ENV", raising=False)
    monkeypatch.delenv("KOKONUT_ENV", raising=False)
    monkeypatch.delenv("FALLBACK_SECRET", raising=False)
    monkeypatch.delenv("LOADED_SECRET", raising=False)


def test_sops_failure_does_not_fall_back_in_production(monkeypatch, tmp_path):
    _reset_loader(monkeypatch, tmp_path)
    monkeypatch.setenv("KOKONUT_ENV", "production")
    (tmp_path / ".env.sops").write_text("encrypted")
    (tmp_path / ".env").write_text("FALLBACK_SECRET=plaintext\n")
    monkeypatch.setattr(
        env.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, "sops")
        ),
    )

    with pytest.raises(env.SecretLoadError, match="SOPS decryption failed"):
        env.load_dotenv()
    assert "FALLBACK_SECRET" not in env.os.environ
    assert env._LOADED is False


def test_development_plaintext_fallback_requires_explicit_flag(monkeypatch, tmp_path):
    _reset_loader(monkeypatch, tmp_path)
    monkeypatch.setenv("KOKONUT_ENV", "ci")
    monkeypatch.setenv("KOKONUT_ALLOW_PLAINTEXT_ENV", "true")
    monkeypatch.setenv("PG_HOST", "database")
    monkeypatch.setenv("PG_DB", "kokonut_intelligence")
    monkeypatch.setenv("PG_USER", "kokonut")
    monkeypatch.setenv("PG_PASSWORD", "test-password")
    (tmp_path / ".env.sops").write_text("encrypted")
    (tmp_path / ".env").write_text("FALLBACK_SECRET=plaintext\n")
    monkeypatch.setattr(
        env.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )

    env.load_dotenv()

    assert env.os.environ["FALLBACK_SECRET"] == "plaintext"
    assert env._LOADED is True


def test_dotenv_parser_rejects_invalid_variable_names(monkeypatch):
    monkeypatch.delenv("BAD-NAME", raising=False)

    with pytest.raises(env.SecretLoadError, match="variable name"):
        env._parse_dotenv("BAD-NAME=value")


def test_missing_secret_source_fails_for_ci(monkeypatch, tmp_path):
    _reset_loader(monkeypatch, tmp_path)
    monkeypatch.setenv("KOKONUT_ENV", "ci")

    with pytest.raises(env.SecretLoadError, match="source found"):
        env.load_dotenv()


def test_injected_ci_environment_does_not_require_dotenv_file(monkeypatch, tmp_path):
    _reset_loader(monkeypatch, tmp_path)
    monkeypatch.setenv("KOKONUT_ENV", "ci")
    monkeypatch.setenv("PG_HOST", "database")
    monkeypatch.setenv("PG_DB", "kokonut_intelligence")
    monkeypatch.setenv("PG_USER", "kokonut")
    monkeypatch.setenv("PG_PASSWORD", "ci-password")

    env.load_dotenv()

    assert env._LOADED is True


def test_plaintext_requires_explicit_opt_in_in_development(monkeypatch, tmp_path):
    _reset_loader(monkeypatch, tmp_path)
    monkeypatch.setenv("KOKONUT_ENV", "development")
    (tmp_path / ".env").write_text("FALLBACK_SECRET=plaintext\n")

    with pytest.raises(env.SecretLoadError, match="explicit development opt-in"):
        env.load_dotenv()
    assert env._LOADED is False


def test_production_rejects_placeholder_credentials(monkeypatch, tmp_path):
    _reset_loader(monkeypatch, tmp_path)
    monkeypatch.setenv("KOKONUT_ENV", "production")
    monkeypatch.setenv("PG_HOST", "database")
    monkeypatch.setenv("PG_DB", "kokonut_intelligence")
    monkeypatch.setenv("PG_USER", "kokonut")
    monkeypatch.setenv("PG_PASSWORD", "replace-with-strong-password-min-24-chars")
    (tmp_path / ".env.sops").write_text("encrypted")
    monkeypatch.setattr(env.subprocess, "run", lambda *args, **kwargs: type(
        "Result", (), {"stdout": ""}
    )())

    with pytest.raises(env.SecretLoadError, match="placeholder"):
        env.load_dotenv()
    assert env._LOADED is False
