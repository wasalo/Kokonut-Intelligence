"""Tests for stream processor, security, federation, sandbox, and gateway."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# Stream Processor Tests
# ---------------------------------------------------------------------------

class TestStreamProcessor:
    def test_ingest_inserts_buffer(self):
        from services.stream.processor import StreamProcessor

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        processor = StreamProcessor(conn=mock_conn)
        entry_id = processor.ingest(str(uuid.uuid4()), "soil_moisture", 25.3, "pct")
        assert entry_id is not None

    def test_stats_structure(self):
        from services.stream.processor import StreamProcessor

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            (100, 5, 95, datetime.now(timezone.utc), datetime.now(timezone.utc)),
            (2, 10),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        processor = StreamProcessor(conn=mock_conn)
        stats = processor.stats()
        assert "buffer" in stats
        assert "alerts" in stats


class TestWindowAggregator:
    def test_get_window_bounds(self):
        from services.stream.windows import WindowAggregator

        agg = WindowAggregator()
        ts = datetime(2026, 7, 12, 10, 23, 0, tzinfo=timezone.utc)
        start, end = agg._get_window_bounds(ts, "5min")
        assert start.minute == 20
        assert end.minute == 25

    def test_window_sizes(self):
        from services.stream.windows import WINDOW_SIZES
        assert "1min" in WINDOW_SIZES
        assert "5min" in WINDOW_SIZES
        assert "15min" in WINDOW_SIZES
        assert "1hour" in WINDOW_SIZES


class TestStreamAlertEvaluator:
    def test_evaluate_threshold_gt(self):
        from services.stream.alerts import StreamAlertEvaluator

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        evaluator = StreamAlertEvaluator(conn=mock_conn)
        # value=50 > threshold=30 → should trigger
        alert_id = evaluator.evaluate_threshold(
            str(uuid.uuid4()), "soil_moisture", 50.0, 30.0, operator="gt"
        )
        assert alert_id is not None

    def test_evaluate_threshold_no_trigger(self):
        from services.stream.alerts import StreamAlertEvaluator

        evaluator = StreamAlertEvaluator(conn=MagicMock())
        alert_id = evaluator.evaluate_threshold(
            str(uuid.uuid4()), "soil_moisture", 10.0, 30.0, operator="gt"
        )
        assert alert_id is None


# ---------------------------------------------------------------------------
# Security Tests
# ---------------------------------------------------------------------------

class TestCapabilityManager:
    def test_hash_token(self):
        from services.security.capabilities import CapabilityManager
        h1 = CapabilityManager._hash_token("test_token")
        h2 = CapabilityManager._hash_token("test_token")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_issue_token(self):
        from services.security.capabilities import CapabilityManager

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        manager = CapabilityManager(conn=mock_conn)
        result = manager.issue(
            holder="test_agent",
            capabilities=[{"resource": "harvest_event", "action": "write"}],
        )
        assert "token" in result
        assert result["holder"] == "test_agent"

    def test_verify_revoked_token(self):
        from services.security.capabilities import CapabilityManager

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            str(uuid.uuid4()), "agent", [{"resource": "r", "action": "a"}],
            datetime.now(timezone.utc), None, 0, True  # revoked=True
        )
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        manager = CapabilityManager(conn=mock_conn)
        result = manager.verify("any_token", "r", "a")
        assert result is None


class TestAuditLogger:
    def test_log_access(self):
        from services.security.audit import AuditLogger

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        audit = AuditLogger(conn=mock_conn)
        log_id = audit.log_access("test_user", "harvest_event", "write", "allowed")
        assert log_id is not None


# ---------------------------------------------------------------------------
# Federation Tests
# ---------------------------------------------------------------------------

class TestFederationNode:
    def test_register_node(self):
        from services.federation.node import FederationNode

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (str(uuid.uuid4()),)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        node = FederationNode(conn=mock_conn)
        node_id = node.register("farm_b", "https://farm-b.example.com")
        assert node_id is not None


class TestFederationProtocol:
    def test_submit_query(self):
        from services.federation.protocol import FederationProtocol

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            (str(uuid.uuid4()),),  # node lookup
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        protocol = FederationProtocol(conn=mock_conn)
        query_id = protocol.query("regional_soil", {"region": "east"})
        assert query_id is not None


# ---------------------------------------------------------------------------
# Sandbox Tests
# ---------------------------------------------------------------------------

class TestAnalysisEnvironment:
    def test_create_env(self):
        from services.sandbox.environment import AnalysisEnvironment

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        env = AnalysisEnvironment(conn=mock_conn)
        env_id = env.create(str(uuid.uuid4()), env_type="sandbox")
        assert env_id is not None

    def test_list_environments(self):
        from services.sandbox.environment import AnalysisEnvironment

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        env = AnalysisEnvironment(conn=mock_conn)
        envs = env.list_environments()
        assert envs == []


class TestIsolationGuard:
    def test_validate_query_rejects_drop(self):
        from services.sandbox.isolation import IsolationGuard

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (["location"], ["capability_token"], 10000, 300, False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        guard = IsolationGuard(conn=mock_conn)
        allowed, reason = guard.validate_query(str(uuid.uuid4()), "DROP TABLE location")
        assert not allowed
        assert "DROP" in reason

    def test_validate_query_allows_select(self):
        from services.sandbox.isolation import IsolationGuard

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (["location"], [], 10000, 300, False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        guard = IsolationGuard(conn=mock_conn)
        allowed, reason = guard.validate_query(str(uuid.uuid4()), "SELECT * FROM location LIMIT 10")
        assert allowed


# ---------------------------------------------------------------------------
# Gateway Tests
# ---------------------------------------------------------------------------

class TestGatewayRateLimiter:
    def test_check_within_limit(self):
        from services.gateway.rate_limiter import RateLimiter

        limiter = RateLimiter(max_tokens=10, refill_rate=100)
        assert limiter.check("caller1") is True

    def test_check_exceeds_limit(self):
        from services.gateway.rate_limiter import RateLimiter

        limiter = RateLimiter(max_tokens=2, refill_rate=0)
        assert limiter.check("caller1") is True
        assert limiter.check("caller1") is True
        assert limiter.check("caller1") is False  # exhausted

    def test_get_status(self):
        from services.gateway.rate_limiter import RateLimiter

        limiter = RateLimiter(max_tokens=50)
        status = limiter.get_status("caller1")
        assert status["max_tokens"] == 50
        assert status["tokens_available"] <= 50


class TestGatewayAuth:
    def test_verify_request_no_auth(self):
        from services.gateway.auth import verify_request

        mock_request = MagicMock()
        mock_request.headers = {}
        result = verify_request(mock_request)
        assert result["authenticated"] is True  # anonymous read access
        assert result["caller"] == "anonymous"


# ---------------------------------------------------------------------------
# CLI Import Tests
# ---------------------------------------------------------------------------

class TestCLIModules:
    def test_stream_cli(self):
        from services.stream.cli import main
        assert callable(main)

    def test_security_cli(self):
        from services.security.cli import main
        assert callable(main)

    def test_federation_cli(self):
        from services.federation.cli import main
        assert callable(main)

    def test_sandbox_cli(self):
        from services.sandbox.cli import main
        assert callable(main)

    def test_gateway_cli(self):
        from services.gateway.cli import main
        assert callable(main)
