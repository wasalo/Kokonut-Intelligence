"""Regression tests for daily on-chain commodity price attestation."""

from services.ingestion.price_attestation import attest_daily_prices


class _Cursor:
    def __init__(self):
        self.query = None
        self.closed = False

    def execute(self, query):
        self.query = query

    def fetchall(self):
        return []

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor()

    def cursor(self, **_kwargs):
        return self.cursor_instance


def test_daily_price_attestation_handles_no_pending_prices():
    conn = _Connection()

    result = attest_daily_prices(conn)

    assert result == {"status": "success", "prices_attested": 0, "results": []}
    assert conn.cursor_instance.closed
