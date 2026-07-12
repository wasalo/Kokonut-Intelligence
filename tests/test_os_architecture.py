"""Tests for Event Bus, Task Scheduler, and Computation Cache."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Event Bus Tests
# ---------------------------------------------------------------------------

class TestEventBus:
    """Unit tests for services.events.bus.EventBus."""

    def test_publish_inserts_event(self):
        """publish() inserts a row into platform_event."""
        from services.events.bus import EventBus

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        bus = EventBus(conn=mock_conn)
        event_id = bus.publish(
            "sensor_reading",
            {"sensor_id": "s1", "value": 25.3},
            source_table="sensor_reading",
            source_id="test-id",
            priority="high",
        )

        assert event_id is not None
        assert isinstance(event_id, str)
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        assert "platform_event" in call_args[0][0]
        mock_conn.commit.assert_called_once()

    def test_publish_rollback_on_error(self):
        """publish() rolls back on exception."""
        from services.events.bus import EventBus

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB error")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        bus = EventBus(conn=mock_conn)
        with pytest.raises(Exception, match="DB error"):
            bus.publish("test_event", {"key": "value"})
        mock_conn.rollback.assert_called_once()

    def test_process_pending_handles_empty(self):
        """process_pending() returns zero stats when no pending events."""
        from services.events.bus import EventBus

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        bus = EventBus(conn=mock_conn)
        stats = bus.process_pending(batch_size=10)
        assert stats == {"processed": 0, "failed": 0, "skipped": 0}

    def test_process_pending_skips_event_without_handlers(self):
        """Events with no registered handlers are marked skipped."""
        from services.events.bus import EventBus

        event_id = str(uuid.uuid4())
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # First call: fetch pending events. Second call: fetch handlers (empty).
        mock_cursor.fetchall.side_effect = [
            [(event_id, "no_handler_event", "{}", 0, 3)],
            [],
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        bus = EventBus(conn=mock_conn)
        stats = bus.process_pending(batch_size=10)
        assert stats["skipped"] == 1

    def test_cleanup_old_events(self):
        """cleanup_old_events() deletes old completed/dead_letter events."""
        from services.events.bus import EventBus

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        bus = EventBus(conn=mock_conn)
        deleted = bus.cleanup_old_events(days=30)
        assert deleted == 5

    def test_get_stats(self):
        """get_stats() returns status counts."""
        from services.events.bus import EventBus

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("completed", 10), ("pending", 3)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        bus = EventBus(conn=mock_conn)
        stats = bus.get_stats()
        assert stats == {"completed": 10, "pending": 3}


# ---------------------------------------------------------------------------
# Scheduler Parser Tests
# ---------------------------------------------------------------------------

class TestSchedulerParser:
    """Unit tests for services.scheduler.parser."""

    def test_parse_cron_every_minute(self):
        from services.scheduler.parser import parse_cron

        result = parse_cron("* * * * *")
        assert result["minute"] == set(range(0, 60))
        assert result["hour"] == set(range(0, 24))

    def test_parse_cron_specific_values(self):
        from services.scheduler.parser import parse_cron

        result = parse_cron("0 6 * * *")
        assert result["minute"] == {0}
        assert result["hour"] == {6}

    def test_parse_cron_step(self):
        from services.scheduler.parser import parse_cron

        result = parse_cron("*/15 * * * *")
        assert result["minute"] == {0, 15, 30, 45}

    def test_parse_cron_range(self):
        from services.scheduler.parser import parse_cron

        result = parse_cron("0 9-17 * * *")
        assert result["hour"] == set(range(9, 18))

    def test_parse_cron_invalid(self):
        from services.scheduler.parser import parse_cron

        with pytest.raises(ValueError, match="Invalid cron"):
            parse_cron("invalid")

    def test_next_run_time(self):
        from services.scheduler.parser import next_run_time

        after = datetime(2026, 7, 12, 5, 30, tzinfo=timezone.utc)
        nxt = next_run_time("0 6 * * *", after=after)
        assert nxt.hour == 6
        assert nxt.minute == 0
        assert nxt > after

    def test_describe_cron(self):
        from services.scheduler.parser import describe_cron

        desc = describe_cron("0 6 * * *")
        assert "6" in desc


# ---------------------------------------------------------------------------
# Scheduler Engine Tests
# ---------------------------------------------------------------------------

class TestSchedulerEngine:
    """Unit tests for services.scheduler.engine.SchedulerEngine."""

    def test_tick_no_tasks(self):
        """tick() returns zero stats when no tasks are due."""
        from services.scheduler.engine import SchedulerEngine

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        engine = SchedulerEngine(mock_conn, worker_id="test-worker")
        stats = engine.tick()
        assert stats == {"launched": 0, "skipped": 0, "no_resources": 0}

    def test_get_status(self):
        """get_status() returns task counts and task list."""
        from services.scheduler.engine import SchedulerEngine

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # First call: counts. Second call: task list.
        mock_cursor.fetchone.return_value = (5, 1, 0, 0)
        mock_cursor.fetchall.return_value = [
            ("weather_ingestion", "services.ingestion.weather", "0 */6 * * *", "normal", None, None, None, 0),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        engine = SchedulerEngine(mock_conn, worker_id="test-worker")
        status = engine.get_status()
        assert status["worker_id"] == "test-worker"
        assert status["tasks"]["enabled"] == 5
        assert len(status["task_list"]) == 1


# ---------------------------------------------------------------------------
# Resource Pool Tests
# ---------------------------------------------------------------------------

class TestResourcePool:
    """Unit tests for services.scheduler.resources.ResourcePool."""

    def test_acquire_success(self):
        from services.scheduler.resources import ResourcePool

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5, 1)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        pool = ResourcePool(mock_conn)
        result = pool.acquire("db_connection")
        assert result is True

    def test_acquire_failure(self):
        from services.scheduler.resources import ResourcePool

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        pool = ResourcePool(mock_conn)
        result = pool.acquire("db_connection")
        assert result is False

    def test_release(self):
        from services.scheduler.resources import ResourcePool

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        pool = ResourcePool(mock_conn)
        pool.release("db_connection")
        mock_cursor.execute.assert_called_once()

    def test_get_status(self):
        from services.scheduler.resources import ResourcePool

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("db_connection", "database", 5, 2, 300),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        pool = ResourcePool(mock_conn)
        status = pool.get_status()
        assert len(status) == 1
        assert status[0]["name"] == "db_connection"
        assert status[0]["running"] == 2


# ---------------------------------------------------------------------------
# Computation Cache Tests
# ---------------------------------------------------------------------------

class TestComputationCache:
    """Unit tests for services.cache.cache.ComputationCache."""

    def test_make_key_deterministic(self):
        """Cache keys are deterministic for same inputs."""
        from services.cache.cache import ComputationCache

        cache = ComputationCache()
        key1 = cache._make_key("metric", "loc-1", {"period": "2026-Q1"})
        key2 = cache._make_key("metric", "loc-1", {"period": "2026-Q1"})
        assert key1 == key2

    def test_make_key_varies_by_type(self):
        from services.cache.cache import ComputationCache

        cache = ComputationCache()
        key1 = cache._make_key("metric", "loc-1", {})
        key2 = cache._make_key("analytics", "loc-1", {})
        assert key1 != key2

    def test_make_key_varies_by_location(self):
        from services.cache.cache import ComputationCache

        cache = ComputationCache()
        key1 = cache._make_key("metric", "loc-1", {})
        key2 = cache._make_key("metric", "loc-2", {})
        assert key1 != key2

    def test_get_returns_none_on_miss(self):
        from services.cache.cache import ComputationCache

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        cache = ComputationCache(conn=mock_conn)
        result = cache.get("metric", "loc-1", {})
        assert result is None

    def test_get_returns_none_on_expired(self):
        """Expired entries are invalidated and return None."""
        from services.cache.cache import ComputationCache

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            str(uuid.uuid4()),
            {"value": 42},
            datetime.now(timezone.utc),
            datetime.now(timezone.utc) - timedelta(hours=1),  # expired
            5,
        )
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        cache = ComputationCache(conn=mock_conn)
        result = cache.get("metric", "loc-1", {})
        assert result is None

    def test_set_inserts_cache_entry(self):
        from services.cache.cache import ComputationCache

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        cache = ComputationCache(conn=mock_conn)
        key = cache.set("metric", {"value": 42}, location_id="loc-1")
        assert key is not None
        assert "metric" in key
        assert "loc-1" in key

    def test_invalidate(self):
        from services.cache.cache import ComputationCache

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 3
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        cache = ComputationCache(conn=mock_conn)
        count = cache.invalidate(computation_type="metric", location_id="loc-1")
        assert count == 3

    def test_cleanup_expired(self):
        from services.cache.cache import ComputationCache

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 7
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        cache = ComputationCache(conn=mock_conn)
        deleted = cache.cleanup_expired()
        assert deleted == 7

    def test_stats(self):
        from services.cache.cache import ComputationCache

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # First call: aggregate stats. Second call: by_type breakdown.
        mock_cursor.fetchone.return_value = (100, 80, 20, 500, 5.0, 102400, 10)
        mock_cursor.fetchall.return_value = [("metric", 50, 300), ("analytics", 30, 200)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        cache = ComputationCache(conn=mock_conn)
        stats = cache.stats()
        assert stats["total_entries"] == 100
        assert stats["valid_entries"] == 80
        assert stats["total_hits"] == 500
        assert len(stats["by_type"]) == 2


# ---------------------------------------------------------------------------
# Event Handler Tests
# ---------------------------------------------------------------------------

class TestEventHandlers:
    """Unit tests for services.events.handlers and services.cache.events."""

    def test_handle_alert_notification(self):
        """Alert notification handler runs without error."""
        from services.events.handlers import handle_alert_notification

        # Should not raise even without env vars
        handle_alert_notification("threshold_breached", {
            "severity": "warning",
            "metric": "soil_moisture",
            "value": 12.0,
            "threshold": 15.0,
            "sensor_device_id": "test-sensor",
        })

    def test_cache_event_handlers_exist(self):
        """Cache event handlers are importable."""
        from services.cache.events import (
            handle_metric_computed,
            handle_crisp_scored,
            handle_sensor_reading,
            handle_harvest_recorded,
        )
        assert callable(handle_metric_computed)
        assert callable(handle_crisp_scored)
        assert callable(handle_sensor_reading)
        assert callable(handle_harvest_recorded)
