"""Bounded, durable per-instance journal for gateway audit records.

The journal uses only Python's SQLite standard library. Deployments that need
recovery across container replacement must mount a private local volume at the
configured path. Do not place this database on a multi-host network filesystem.
"""

from __future__ import annotations

import atexit
import errno
import fcntl
import json
import os
import sqlite3
import stat
import threading
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

DEFAULT_MAX_PENDING = 10_000
MAX_EVENT_BYTES = 16_384
INITIALIZATION_BUSY_RETRIES = 8
DEFAULT_ALERT_PERCENT = 80


def _initialize_statement(conn: sqlite3.Connection, statement: str) -> None:
    """Retry brief SQLite initialization lock races between first writers."""
    for attempt in range(INITIALIZATION_BUSY_RETRIES):
        try:
            conn.execute(statement)
            return
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if "locked" not in message and "busy" not in message:
                raise
            if attempt + 1 == INITIALIZATION_BUSY_RETRIES:
                raise
            time.sleep(min(0.01 * (2**attempt), 0.25))


class AuditSpoolError(RuntimeError):
    """The local audit journal could not safely retain an event."""


class AuditSpoolFull(AuditSpoolError):
    """The configured pending-event bound has been reached."""


class GatewayAuditSpool:
    """Persist failed gateway audit writes until PostgreSQL is available."""

    def __init__(self, path: str | None = None, max_pending: int | None = None):
        configured_path = path or os.environ.get("KOKONUT_GATEWAY_AUDIT_SPOOL_PATH")
        if configured_path:
            self.path = Path(configured_path).expanduser()
        else:
            state_home = Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser()
            self.path = state_home / "kokonut" / "gateway-audit.sqlite3"

        if max_pending is None:
            raw_max = os.environ.get("KOKONUT_GATEWAY_AUDIT_SPOOL_MAX_EVENTS", str(DEFAULT_MAX_PENDING))
            try:
                max_pending = int(raw_max)
            except (TypeError, ValueError) as exc:
                raise ValueError("KOKONUT_GATEWAY_AUDIT_SPOOL_MAX_EVENTS must be a positive integer") from exc
        if isinstance(max_pending, bool) or not isinstance(max_pending, int) or max_pending <= 0:
            raise ValueError("max_pending must be a positive integer")
        self.max_pending = max_pending
        raw_threshold = os.environ.get("KOKONUT_GATEWAY_AUDIT_SPOOL_ALERT_THRESHOLD")
        if raw_threshold is None:
            self.alert_threshold = max(1, (max_pending * DEFAULT_ALERT_PERCENT + 99) // 100)
        else:
            try:
                configured_threshold = int(raw_threshold)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "KOKONUT_GATEWAY_AUDIT_SPOOL_ALERT_THRESHOLD must be 0 or a positive integer"
                ) from exc
            if configured_threshold == 0:
                self.alert_threshold = max(1, (max_pending * DEFAULT_ALERT_PERCENT + 99) // 100)
            elif 1 <= configured_threshold <= self.max_pending:
                self.alert_threshold = configured_threshold
            else:
                raise ValueError("alert threshold must be 0 or between 1 and max_pending")
        self._owner_id: str | None = None
        self._owner_pid = os.getpid()
        self._owner_lock_fd: int | None = None
        self._reservation_lock = threading.RLock()
        self._reservation_ids: set[str] = set()

    def _refresh_process_owner(self) -> None:
        """Do not reuse an advisory lock identity inherited across `fork()`.

        Closing the child's duplicate descriptor without `LOCK_UN` leaves the
        parent's open file description and lock intact.
        """
        process_id = os.getpid()
        if process_id == self._owner_pid:
            return
        descriptor = self._owner_lock_fd
        self._owner_id = None
        self._owner_pid = process_id
        self._owner_lock_fd = None
        self._reservation_ids.clear()
        if descriptor is not None:
            os.close(descriptor)

    def _connect(self) -> sqlite3.Connection:
        if self.path.parent.is_symlink():
            raise AuditSpoolError("gateway audit journal directory cannot be a symlink")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        parent_stat = self.path.parent.stat()
        if parent_stat.st_uid != os.geteuid() or parent_stat.st_mode & 0o077:
            raise AuditSpoolError("gateway audit journal directory must be private and owned by this process")
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | no_follow, 0o600)
        try:
            file_stat = os.fstat(descriptor)
            if file_stat.st_uid != os.geteuid():
                raise AuditSpoolError("gateway audit journal file must be owned by this process")
            if stat.S_IMODE(file_stat.st_mode) & 0o077:
                os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)

        conn = sqlite3.connect(str(self.path), timeout=5)
        try:
            conn.execute("PRAGMA busy_timeout = 5000")
            _initialize_statement(conn, "PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = FULL")
            _initialize_statement(
                conn,
                """CREATE TABLE IF NOT EXISTS pending_gateway_audit (
                       sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                       event_id TEXT NOT NULL UNIQUE,
                       payload_json TEXT NOT NULL,
                       queued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                   )"""
            )
            _initialize_statement(
                conn,
                """CREATE TABLE IF NOT EXISTS gateway_mutation_reservation (
                       reservation_id TEXT PRIMARY KEY,
                       owner_id TEXT NOT NULL,
                       created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                   )"""
            )
            return conn
        except Exception:
            conn.close()
            raise

    def _owner_lock_path(self, owner_id: str) -> Path:
        try:
            canonical_id = str(UUID(owner_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise AuditSpoolError("gateway audit reservation owner identity is invalid") from exc
        return self.path.parent / f".{self.path.name}.owner-{canonical_id}.lock"

    def _ensure_owner_lock(self) -> str:
        self._refresh_process_owner()
        if self._owner_id is not None and self._owner_lock_fd is not None:
            return self._owner_id

        conn = self._connect()
        conn.close()
        owner_id = str(uuid4())
        lock_path = self._owner_lock_path(owner_id)
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            file_stat = os.fstat(descriptor)
            if file_stat.st_uid != os.geteuid():
                raise AuditSpoolError("gateway audit reservation lock must be owned by this process")
            if stat.S_IMODE(file_stat.st_mode) & 0o077:
                os.fchmod(descriptor, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            os.close(descriptor)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
            raise

        self._owner_id = owner_id
        self._owner_lock_fd = descriptor
        atexit.register(self._close_owner_lock)
        return owner_id

    def _close_owner_lock(self) -> None:
        descriptor = self._owner_lock_fd
        owner_id = self._owner_id
        self._owner_lock_fd = None
        self._owner_id = None
        self._reservation_ids.clear()
        if descriptor is None:
            return
        lock_path = self._owner_lock_path(owner_id) if owner_id is not None else None
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
        if lock_path is not None:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def _close_owner_lock_if_idle(self, conn: sqlite3.Connection) -> None:
        if self._owner_id is None or self._reservation_ids:
            return
        remaining = int(
            conn.execute(
                "SELECT COUNT(*) FROM gateway_mutation_reservation WHERE owner_id = ?",
                (self._owner_id,),
            ).fetchone()[0]
        )
        if remaining == 0:
            self._close_owner_lock()

    def _owner_lock_is_live(self, owner_id: str) -> bool:
        lock_path = self._owner_lock_path(owner_id)
        try:
            descriptor = os.open(lock_path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        except FileNotFoundError:
            return False
        try:
            file_stat = os.fstat(descriptor)
            if file_stat.st_uid != os.geteuid() or stat.S_IMODE(file_stat.st_mode) & 0o077:
                raise AuditSpoolError("gateway audit reservation lock permissions are unsafe")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK}:
                    return True
                raise
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
            return False
        finally:
            os.close(descriptor)

    def _prune_stale_reservations(self, conn: sqlite3.Connection) -> int:
        rows = conn.execute(
            "SELECT reservation_id, owner_id FROM gateway_mutation_reservation"
        ).fetchall()
        removed = 0
        for reservation_id, owner_id in rows:
            if owner_id == self._owner_id:
                if reservation_id not in self._reservation_ids:
                    cursor = conn.execute(
                        "DELETE FROM gateway_mutation_reservation WHERE reservation_id = ?",
                        (reservation_id,),
                    )
                    removed += cursor.rowcount
                continue
            if not self._owner_lock_is_live(owner_id):
                cursor = conn.execute(
                    "DELETE FROM gateway_mutation_reservation WHERE owner_id = ?",
                    (owner_id,),
                )
                removed += cursor.rowcount
        return removed

    def prune_stale_reservations(self) -> int:
        """Remove reservations whose owning process no longer holds its lock."""
        with self._reservation_lock:
            self._refresh_process_owner()
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                removed = self._prune_stale_reservations(conn)
                conn.commit()
                self._close_owner_lock_if_idle(conn)
                return removed
            except Exception:
                if conn.in_transaction:
                    conn.rollback()
                raise
            finally:
                conn.close()

    def reserve_mutation(self) -> str | None:
        """Atomically reserve one journal-threshold slot across local processes."""
        with self._reservation_lock:
            owner_id = self._ensure_owner_lock()
            reservation_id = str(uuid4())
            try:
                conn = self._connect()
            except Exception:
                if not self._reservation_ids:
                    self._close_owner_lock()
                raise
            try:
                conn.execute("BEGIN IMMEDIATE")
                self._prune_stale_reservations(conn)
                pending = int(
                    conn.execute("SELECT COUNT(*) FROM pending_gateway_audit").fetchone()[0]
                )
                active = int(
                    conn.execute("SELECT COUNT(*) FROM gateway_mutation_reservation").fetchone()[0]
                )
                if pending + active >= self.alert_threshold:
                    conn.rollback()
                    if not self._reservation_ids:
                        self._close_owner_lock()
                    return None
                conn.execute(
                    "INSERT INTO gateway_mutation_reservation (reservation_id, owner_id) VALUES (?, ?)",
                    (reservation_id, owner_id),
                )
                conn.commit()
                self._reservation_ids.add(reservation_id)
                return reservation_id
            except Exception:
                if conn.in_transaction:
                    conn.rollback()
                if not self._reservation_ids:
                    self._close_owner_lock()
                raise
            finally:
                conn.close()

    def release_mutation(self, reservation_id: str) -> None:
        """Release a threshold slot and close its owner lock when no slots remain."""
        with self._reservation_lock:
            self._refresh_process_owner()
            if self._owner_id is None:
                return
            conn = None
            try:
                conn = self._connect()
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "DELETE FROM gateway_mutation_reservation WHERE reservation_id = ? AND owner_id = ?",
                    (reservation_id, self._owner_id),
                )
                remaining = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM gateway_mutation_reservation WHERE owner_id = ?",
                        (self._owner_id,),
                    ).fetchone()[0]
                )
                conn.commit()
                self._reservation_ids.discard(reservation_id)
            except Exception:
                if conn is not None and conn.in_transaction:
                    conn.rollback()
                self._reservation_ids.discard(reservation_id)
                raise
            finally:
                if conn is not None:
                    conn.close()
            if remaining == 0 and not self._reservation_ids:
                self._close_owner_lock()

    def pending_count(self) -> int:
        if not self.path.exists():
            return 0
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) FROM pending_gateway_audit").fetchone()
            return int(row[0])
        finally:
            conn.close()

    def capacity_status(self, *, ensure_storage: bool = False) -> dict[str, int | bool]:
        """Return queue capacity and alert state without exposing event contents."""
        if self.path.exists() or ensure_storage:
            conn = self._connect()
            try:
                row = conn.execute("SELECT COUNT(*) FROM pending_gateway_audit").fetchone()
                pending_events = int(row[0])
                reservation_row = conn.execute(
                    "SELECT COUNT(*) FROM gateway_mutation_reservation"
                ).fetchone()
                active_reservations = int(reservation_row[0])
                alert_active = pending_events + active_reservations >= self.alert_threshold
                if ensure_storage and not alert_active:
                    probe_id = f"health-probe:{uuid4()}"
                    probe_payload = json.dumps({"event_id": probe_id}, separators=(",", ":"))
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute(
                        "INSERT INTO pending_gateway_audit (event_id, payload_json) VALUES (?, ?)",
                        (probe_id, probe_payload),
                    )
                    conn.execute(
                        "DELETE FROM pending_gateway_audit WHERE event_id = ?", (probe_id,)
                    )
                    conn.commit()
            finally:
                if conn.in_transaction:
                    conn.rollback()
                conn.close()
        else:
            pending_events = 0
            active_reservations = 0
        alert_active = pending_events + active_reservations >= self.alert_threshold
        return {
            "pending_events": pending_events,
            "active_mutation_reservations": active_reservations,
            "max_pending_events": self.max_pending,
            "alert_threshold_events": self.alert_threshold,
            "alert_active": alert_active,
            "write_restricted": alert_active,
        }

    def enqueue(self, event: dict[str, Any]) -> int:
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("gateway audit event_id is required")
        payload = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if len(payload.encode("utf-8")) > MAX_EVENT_BYTES:
            raise AuditSpoolError("gateway audit event exceeds the local journal size limit")

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            exists = conn.execute(
                "SELECT 1 FROM pending_gateway_audit WHERE event_id = ?", (event_id,)
            ).fetchone()
            if exists:
                conn.commit()
                return int(conn.execute("SELECT COUNT(*) FROM pending_gateway_audit").fetchone()[0])
            count = int(conn.execute("SELECT COUNT(*) FROM pending_gateway_audit").fetchone()[0])
            if count >= self.max_pending:
                conn.rollback()
                raise AuditSpoolFull("gateway audit journal has reached its configured event limit")
            conn.execute(
                "INSERT INTO pending_gateway_audit (event_id, payload_json) VALUES (?, ?)",
                (event_id, payload),
            )
            conn.commit()
            return count + 1
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def pending(self, limit: int = 100) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer")
        if not self.path.exists():
            return []
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT event_id, payload_json FROM pending_gateway_audit
                   ORDER BY sequence ASC LIMIT ?""",
                (limit,),
            ).fetchall()
        finally:
            conn.close()
        events = []
        for event_id, payload_json in rows:
            event = json.loads(payload_json)
            if event.get("event_id") != event_id:
                raise AuditSpoolError("gateway audit journal event identity mismatch")
            events.append(event)
        return events

    def acknowledge(self, event_id: str) -> bool:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                "DELETE FROM pending_gateway_audit WHERE event_id = ?", (event_id,)
            )
            conn.commit()
            return cursor.rowcount == 1
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()
