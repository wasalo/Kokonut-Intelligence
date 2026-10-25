"""The standalone AI-summary CLI scopes inspection before worker dispatch."""

from __future__ import annotations

import sys

import pytest

from services.agents import ai_summary, worker_cli

LOCATION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_LOCATION_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
SUMMARY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _set_argv(monkeypatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["ai_summary", *arguments])


def test_missing_mode_fails_before_worker_dispatch(monkeypatch, capsys) -> None:
    _set_argv(monkeypatch)
    monkeypatch.setattr(
        ai_summary, "run_ai_summary", lambda *_a, **_k: pytest.fail("worker dispatched")
    )

    with pytest.raises(SystemExit, match="2"):
        ai_summary.main()

    assert "--location-id is required" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments",
    [
        ("--location-id", "not-a-uuid"),
        ("--list", "--location-id", "not-a-uuid"),
        ("--verify", SUMMARY_ID, "--location-id", "not-a-uuid"),
        ("--verify", "not-a-uuid", "--location-id", LOCATION_ID),
    ],
)
def test_malformed_identifier_fails_before_worker_dispatch(monkeypatch, arguments) -> None:
    _set_argv(monkeypatch, *arguments)
    monkeypatch.setattr(
        ai_summary, "run_ai_summary", lambda *_a, **_k: pytest.fail("worker dispatched")
    )
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary_list_result",
        lambda *_a, **_k: pytest.fail("list worker dispatched"),
    )
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary_digest_result",
        lambda *_a, **_k: pytest.fail("digest worker dispatched"),
    )

    with pytest.raises(SystemExit, match="2"):
        ai_summary.main()


def test_summary_generation_uses_validated_runner(monkeypatch, capsys) -> None:
    _set_argv(monkeypatch, "--location-id", LOCATION_ID)
    calls = []

    def run(location_id, summary_type, store=False, request_id=None):
        calls.append((location_id, summary_type, store, request_id))
        return {
            "summary": {
                "summary_type": summary_type,
                "source_tables": ["harvest_event"],
                "content": "Synthetic summary",
            }
        }

    monkeypatch.setattr(ai_summary, "run_ai_summary", run)
    ai_summary.main()

    assert calls == [(LOCATION_ID, "combined", False, None)]
    assert "Generating combined summary" in capsys.readouterr().out


def test_store_uses_explicit_retry_id_and_omits_content_from_cli_output(
    monkeypatch, capsys
):
    request_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    _set_argv(
        monkeypatch,
        "--location-id",
        LOCATION_ID,
        "--store",
        "--request-id",
        request_id,
    )
    calls = []

    def run(location_id, summary_type, store=False, request_id=None):
        calls.append((location_id, summary_type, store, request_id))
        return {
            "summary": {
                "summary_type": summary_type,
                "source_tables": ["harvest_event"],
                "content": "Private synthetic summary",
            },
            "ai_summary_id": SUMMARY_ID,
        }

    monkeypatch.setattr(ai_summary, "run_ai_summary", run)
    ai_summary.main()

    output = capsys.readouterr().out
    assert calls == [(LOCATION_ID, "combined", True, request_id)]
    assert f"Request ID: {request_id}" in output
    assert f"Summary stored: {SUMMARY_ID}" in output
    assert "Private synthetic summary" not in output
    assert "Summary content omitted from stdout" in output


def test_store_without_gateway_request_id_fails_before_runner(monkeypatch, capsys):
    _set_argv(monkeypatch, "--location-id", LOCATION_ID, "--store")
    monkeypatch.setattr(
        ai_summary,
        "run_ai_summary",
        lambda *_args, **_kwargs: pytest.fail("missing request dispatched the worker"),
    )

    with pytest.raises(SystemExit, match="2"):
        ai_summary.main()

    assert "--store requires --request-id issued by the authenticated Gateway" in (
        capsys.readouterr().err
    )


def test_malformed_store_request_id_fails_before_runner(monkeypatch):
    _set_argv(monkeypatch, "--location-id", LOCATION_ID, "--store", "--request-id", "bad-id")
    monkeypatch.setattr(
        ai_summary,
        "run_ai_summary",
        lambda *_args, **_kwargs: pytest.fail("invalid request opened the worker path"),
    )

    with pytest.raises(SystemExit, match="2"):
        ai_summary.main()


def test_verify_cannot_be_combined_with_store_before_worker_dispatch(monkeypatch):
    _set_argv(
        monkeypatch,
        "--verify",
        SUMMARY_ID,
        "--location-id",
        LOCATION_ID,
        "--store",
    )
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary_digest_result",
        lambda *_a, **_k: pytest.fail("invalid CLI combination dispatched a worker"),
    )

    with pytest.raises(SystemExit, match="2"):
        ai_summary.main()


def test_list_requires_exact_location_before_worker_dispatch(monkeypatch, capsys):
    _set_argv(monkeypatch, "--list")
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary_list_result",
        lambda *_a, **_k: pytest.fail("unscoped list dispatched a worker"),
    )

    with pytest.raises(SystemExit, match="2"):
        ai_summary.main()

    assert "--list requires --location-id" in capsys.readouterr().err


def test_global_summary_inventory_mode_is_removed(monkeypatch):
    _set_argv(monkeypatch, "--list", "--all-locations")
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary_list_result",
        lambda *_a, **_k: pytest.fail("global inventory dispatched a worker"),
    )

    with pytest.raises(SystemExit, match="2"):
        ai_summary.main()


def test_location_list_uses_worker_and_retains_preview(monkeypatch, capsys):
    _set_argv(monkeypatch, "--list", "--location-id", LOCATION_ID)
    calls = []
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary_list_result",
        lambda location_id: calls.append(location_id)
        or {
            "items": [
                {
                    "id": SUMMARY_ID,
                    "summary_type": "operations",
                    "status": "draft",
                    "created_at": "2026-10-22",
                    "preview": "Location-specific preview",
                }
            ],
            "source_scope": {
                "view": "kokonut_agent_source.ai_summary_list",
                "location_id": LOCATION_ID,
            },
        },
    )

    ai_summary.main()

    output = capsys.readouterr().out
    assert calls == [LOCATION_ID]
    assert (
        "Source scope: kokonut_agent_source.ai_summary_list "
        f"(location {LOCATION_ID})"
    ) in output
    assert "Preview" in output
    assert "Location-specific preview" in output


def test_empty_location_list_prints_query_scope(monkeypatch, capsys):
    _set_argv(monkeypatch, "--list", "--location-id", LOCATION_ID)
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary_list_result",
        lambda location_id: {
            "items": [],
            "source_scope": {
                "view": "kokonut_agent_source.ai_summary_list",
                "location_id": location_id,
            },
        },
    )

    ai_summary.main()

    output = capsys.readouterr().out
    assert "Source scope: kokonut_agent_source.ai_summary_list" in output
    assert f"(location {LOCATION_ID})" in output
    assert "No summaries found." in output


def test_verify_requires_exact_location_before_worker_dispatch(monkeypatch, capsys):
    _set_argv(monkeypatch, "--verify", SUMMARY_ID)
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary_digest_result",
        lambda *_a, **_k: pytest.fail("unscoped digest dispatched a worker"),
    )

    with pytest.raises(SystemExit, match="2"):
        ai_summary.main()

    assert "--verify requires --location-id" in capsys.readouterr().err


def test_verify_uses_exact_location_and_never_prints_summary_content(
    monkeypatch, capsys
):
    _set_argv(monkeypatch, "--verify", SUMMARY_ID, "--location-id", LOCATION_ID)
    calls = []
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary_digest_result",
        lambda location_id, summary_id: calls.append((location_id, summary_id))
        or {
            "item": {
                "id": SUMMARY_ID,
                "summary_type": "operations",
                "status": "draft",
                "model_version": "synthetic-v1",
                "content_sha256": "a" * 64,
                "content_length": 16,
            },
            "source_scope": {
                "view": "kokonut_agent_source.ai_summary_digest",
                "summary_id": summary_id,
                "location_id": location_id,
            },
        },
    )

    ai_summary.main()

    output = capsys.readouterr().out
    assert calls == [(LOCATION_ID, SUMMARY_ID)]
    assert "Source scope: kokonut_agent_source.ai_summary_digest" in output
    assert "Lifecycle verification: not performed (read-only inspection)" in output
    assert f"Content SHA-256 (computed only; not compared): {'a' * 64}" in output
    assert "Content length: 16 chars" in output
    assert "Synthetic summary" not in output


def test_summary_not_found_does_not_disclose_cross_location_existence(
    monkeypatch, capsys
):
    _set_argv(monkeypatch, "--verify", SUMMARY_ID, "--location-id", OTHER_LOCATION_ID)
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary_digest_result",
        lambda location_id, summary_id: {
            "item": None,
            "source_scope": {
                "view": "kokonut_agent_source.ai_summary_digest",
                "summary_id": summary_id,
                "location_id": location_id,
            },
        },
    )

    ai_summary.main()

    output = capsys.readouterr().out
    assert "Summary not found at the requested location" in output
    assert "Source scope: kokonut_agent_source.ai_summary_digest" in output
