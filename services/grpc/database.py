"""Shared query interface and transaction cleanup for pooled RPC connections."""

import sys
from threading import Lock

from services.common.database import DatabaseConnection


class PooledDatabaseFactory:
    """Callable factory retaining the legacy factory/release handler interface.

    Handlers release in finally blocks. An active exception, including a gRPC
    abort, rolls back; successful handler return commits before pool return.
    """

    def __init__(self, pool):
        self._pool = pool
        self._borrowed = {}
        self._lock = Lock()
        self._closing = False
        self._closed = False

    def __call__(self) -> DatabaseConnection:
        with self._lock:
            if self._closing:
                raise RuntimeError("RPC database pool is shutting down")
            raw = self._pool.getconn()
            try:
                conn = DatabaseConnection(raw)
            except Exception:
                self._pool.putconn(raw, close=True)
                raise
            self._borrowed[conn] = raw
        return conn

    def release(self, conn: DatabaseConnection) -> None:
        """Complete the handler transaction and return only this pool's borrow."""
        with self._lock:
            if conn not in self._borrowed:
                raise ValueError("Connection is not borrowed from this factory or was already released")
            raw = self._borrowed[conn]
            try:
                try:
                    if sys.exception() is not None:
                        conn.rollback()
                    else:
                        conn.commit()
                except Exception:
                    # Never recycle an uncertain transaction or broken connection.
                    self._pool.putconn(raw, close=True)
                    raise
                else:
                    self._pool.putconn(raw, close=bool(raw.closed))
            finally:
                self._borrowed.pop(conn)
                self._close_if_drained()

    def close(self) -> None:
        """Stop new borrowing; close physical connections after active releases."""
        with self._lock:
            self._closing = True
            self._close_if_drained()

    def _close_if_drained(self) -> None:
        if self._closing and not self._borrowed and not self._closed:
            self._closed = True
            self._pool.closeall()
