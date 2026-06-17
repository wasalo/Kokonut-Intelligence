"""Ingestion retry decorator tests."""

from services.ingestion.base import retry


def test_retry_succeeds_on_first_attempt():
    calls = {"n": 0}

    @retry(max_retries=3, backoff=0.01)
    def succeed():
        calls["n"] += 1
        return "ok"

    assert succeed() == "ok"
    assert calls["n"] == 1


def test_retry_succeeds_after_transient_failure():
    calls = {"n": 0}

    @retry(max_retries=3, backoff=0.01)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("transient")
        return "recovered"

    assert flaky() == "recovered"
    assert calls["n"] == 2


def test_retry_raises_after_max_attempts():
    calls = {"n": 0}

    @retry(max_retries=2, backoff=0.01)
    def always_fail():
        calls["n"] += 1
        raise ConnectionError("permanent")

    try:
        always_fail()
        raise AssertionError("expected ConnectionError")
    except ConnectionError as exc:
        assert str(exc) == "permanent"
    assert calls["n"] == 2


if __name__ == "__main__":
    test_retry_succeeds_on_first_attempt()
    test_retry_succeeds_after_transient_failure()
    test_retry_raises_after_max_attempts()
    print("All ingestion retry tests passed ✓")
