"""Unit checks for isolated worker PostgreSQL connection setup."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.common import worker_database


def _connection(login: str, *, autocommit: bool = False):
    connection = MagicMock()
    connection.autocommit = autocommit
    cursor = MagicMock()
    cursor.fetchone.return_value = (login,)
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection, cursor


class _TrackedEnvironment(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lookups = []

    def get(self, key, default=None):
        self.lookups.append(key)
        return super().get(key, default)


def test_worker_credential_reads_only_the_named_worker_secret():
    credential = "  opaque-worker-secret-0123456789abcdef  "
    env = _TrackedEnvironment(
        {
            "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": credential,
            "KOKONUT_OTHER_WORKER_WORKER_CREDENTIAL": "x" * 32,
            "WORKER_CREDENTIAL": "x" * 32,
            "PG_PASSWORD": "x" * 32,
        }
    )

    result = worker_database.get_worker_credential("sensor_anomaly", environ=env)

    assert result == credential
    assert env.lookups == ["KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL"]


def test_worker_credential_is_required_and_shared_secrets_do_not_fallback():
    with pytest.raises(
        worker_database.WorkerDatabaseConfigurationError,
        match="KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL",
    ):
        worker_database.get_worker_credential(
            "sensor_anomaly",
            environ={
                "WORKER_CREDENTIAL": "x" * 32,
                "PG_PASSWORD": "x" * 32,
                "KOKONUT_OTHER_WORKER_WORKER_CREDENTIAL": "x" * 32,
            },
        )


@pytest.mark.parametrize("credential", ["x" * 31, "x" * 4097])
def test_worker_credential_rejects_values_outside_byte_bounds(credential):
    with pytest.raises(
        worker_database.WorkerDatabaseConfigurationError,
        match="32 to 4096 UTF-8 bytes",
    ):
        worker_database.get_worker_credential(
            "sensor_anomaly",
            environ={"KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": credential},
        )


@pytest.mark.parametrize("length", [32, 4096])
def test_worker_credential_accepts_exact_byte_bounds(length):
    credential = "x" * length

    assert (
        worker_database.get_worker_credential(
            "sensor_anomaly",
            environ={"KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": credential},
        )
        == credential
    )


def test_worker_credential_bounds_count_utf8_bytes_not_characters():
    credential = "é" * 16

    assert len(credential) == 16
    assert len(credential.encode("utf-8")) == 32
    assert (
        worker_database.get_worker_credential(
            "sensor_anomaly",
            environ={"KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": credential},
        )
        == credential
    )


def test_worker_credential_rejects_invalid_utf8_text_without_exposing_value():
    credential = "x" * 31 + "\ud800"

    with pytest.raises(
        worker_database.WorkerDatabaseConfigurationError,
        match="must contain valid UTF-8 text",
    ) as error:
        worker_database.get_worker_credential(
            "sensor_anomaly",
            environ={"KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": credential},
        )

    assert credential not in str(error.value)


def test_invalid_worker_key_is_rejected_before_secret_lookup():
    env = _TrackedEnvironment({"KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "x" * 32})

    with pytest.raises(ValueError, match="worker_key"):
        worker_database.get_worker_credential("Sensor-Anomaly", environ=env)

    assert env.lookups == []


def test_worker_dsn_is_required_even_when_shared_database_secrets_exist(monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(worker_database.psycopg2, "connect", connect)

    with pytest.raises(
        worker_database.WorkerDatabaseConfigurationError,
        match="KOKONUT_SENSOR_ANOMALY_DATABASE_URL is required",
    ):
        worker_database.get_worker_db(
            "sensor_anomaly",
            environ={
                "PG_USER": "kokonut_runtime",
                "PG_PASSWORD": "shared-password-is-not-a-worker-dsn",
                "POSTGRES_PASSWORD": "admin-password-is-not-a-worker-dsn",
            },
        )

    connect.assert_not_called()


@pytest.mark.parametrize("worker_key", ["", "Sensor", "sensor-anomaly", "../events"])
def test_invalid_worker_key_is_rejected_before_connection(worker_key, monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(worker_database.psycopg2, "connect", connect)

    with pytest.raises(ValueError, match="worker_key"):
        worker_database.get_worker_db(
            worker_key,
            environ={"KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://unused"},
        )

    connect.assert_not_called()


def test_worker_factory_uses_only_the_named_dsn_and_checks_login(monkeypatch):
    connection, cursor = _connection("kokonut_worker_login")
    connect = MagicMock(return_value=connection)
    monkeypatch.setattr(worker_database.psycopg2, "connect", connect)
    dsn = "postgresql://kokonut_worker_login:secret@database/kokonut_intelligence"

    result = worker_database.get_worker_db(
        "sensor_anomaly",
        connect_timeout=12,
        environ={
            "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": dsn,
            "PG_USER": "kokonut_runtime",
            "PG_PASSWORD": "unused-shared-password",
        },
    )

    assert result is connection
    connect.assert_called_once_with(
        dsn,
        connect_timeout=12,
        application_name="kokonut-worker-sensor_anomaly",
    )
    cursor.execute.assert_called_once_with("SELECT current_user")
    connection.close.assert_not_called()


def test_notification_enqueue_factory_requires_its_distinct_login(monkeypatch):
    connection, cursor = _connection("kokonut_notification_enqueue_login")
    connect = MagicMock(return_value=connection)
    monkeypatch.setattr(worker_database.psycopg2, "connect", connect)
    dsn = "postgresql://kokonut_notification_enqueue_login:secret@database/kokonut_intelligence"

    result = worker_database.get_worker_db(
        "notification_enqueue",
        environ={
            "KOKONUT_NOTIFICATION_ENQUEUE_DATABASE_URL": dsn,
            "PG_USER": "kokonut_runtime",
            "PG_PASSWORD": "unused-shared-password",
        },
    )

    assert result is connection
    connect.assert_called_once_with(
        dsn,
        connect_timeout=8,
        application_name="kokonut-worker-notification_enqueue",
    )
    cursor.execute.assert_called_once_with("SELECT current_user")
    connection.close.assert_not_called()


def test_notification_enqueue_factory_rejects_shared_worker_login(monkeypatch):
    connection, _ = _connection("kokonut_worker_login")
    monkeypatch.setattr(worker_database.psycopg2, "connect", MagicMock(return_value=connection))

    with pytest.raises(
        worker_database.WorkerDatabaseConfigurationError,
        match="worker database login must be kokonut_notification_enqueue_login",
    ):
        worker_database.get_worker_db(
            "notification_enqueue",
            environ={
                "KOKONUT_NOTIFICATION_ENQUEUE_DATABASE_URL":
                    "postgresql://kokonut_worker_login:secret@database/kokonut_intelligence"
            },
        )

    connection.close.assert_called_once_with()


def test_market_data_factory_requires_its_dedicated_database_login(monkeypatch):
    connection, cursor = _connection("kokonut_market_data_login")
    connect = MagicMock(return_value=connection)
    monkeypatch.setattr(worker_database.psycopg2, "connect", connect)
    dsn = "postgresql://kokonut_market_data_login:secret@database/kokonut_intelligence"

    result = worker_database.get_worker_db(
        "market_data",
        environ={
            "KOKONUT_MARKET_DATA_DATABASE_URL": dsn,
            "DATABASE_URL": "postgresql://kokonut_runtime:unused@database/kokonut_intelligence",
            "PG_USER": "kokonut_runtime",
            "PG_PASSWORD": "unused-shared-password",
        },
    )

    assert result is connection
    connect.assert_called_once_with(
        dsn,
        connect_timeout=8,
        application_name="kokonut-worker-market_data",
    )
    cursor.execute.assert_called_once_with("SELECT current_user")


def test_market_data_factory_has_no_shared_dsn_fallback(monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(worker_database.psycopg2, "connect", connect)

    with pytest.raises(
        worker_database.WorkerDatabaseConfigurationError,
        match="KOKONUT_MARKET_DATA_DATABASE_URL is required",
    ):
        worker_database.get_worker_db(
            "market_data",
            environ={
                "DATABASE_URL": "postgresql://kokonut_runtime@database/kokonut_intelligence",
                "PG_USER": "kokonut_runtime",
                "PG_PASSWORD": "shared-runtime-secret",
            },
        )

    connect.assert_not_called()


def test_sensor_ingestion_factory_requires_its_dedicated_database_login(monkeypatch):
    connection, cursor = _connection("kokonut_sensor_ingestion_login")
    connect = MagicMock(return_value=connection)
    monkeypatch.setattr(worker_database.psycopg2, "connect", connect)
    dsn = "postgresql://kokonut_sensor_ingestion_login:secret@database/kokonut_intelligence"

    result = worker_database.get_worker_db(
        "sensor_ingestion",
        environ={
            "KOKONUT_SENSOR_INGESTION_DATABASE_URL": dsn,
            "PG_USER": "kokonut_runtime",
            "PG_PASSWORD": "unused-shared-password",
        },
    )

    assert result is connection
    connect.assert_called_once_with(
        dsn,
        connect_timeout=8,
        application_name="kokonut-worker-sensor_ingestion",
    )
    cursor.execute.assert_called_once_with("SELECT current_user")


def test_sensor_ingestion_factory_has_no_shared_dsn_fallback(monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(worker_database.psycopg2, "connect", connect)

    with pytest.raises(
        worker_database.WorkerDatabaseConfigurationError,
        match="KOKONUT_SENSOR_INGESTION_DATABASE_URL is required",
    ):
        worker_database.get_worker_db(
            "sensor_ingestion",
            environ={
                "DATABASE_URL": "postgresql://kokonut_runtime@database/kokonut_intelligence",
                "PG_USER": "kokonut_runtime",
                "PG_PASSWORD": "shared-runtime-secret",
            },
        )

    connect.assert_not_called()


def test_remote_sensing_factory_requires_its_dedicated_database_login(monkeypatch):
    connection, cursor = _connection("kokonut_remote_sensing_login")
    connect = MagicMock(return_value=connection)
    monkeypatch.setattr(worker_database.psycopg2, "connect", connect)
    dsn = "postgresql://kokonut_remote_sensing_login:secret@database/kokonut_intelligence"

    result = worker_database.get_worker_db(
        "remote_sensing",
        environ={
            "KOKONUT_REMOTE_SENSING_DATABASE_URL": dsn,
            "PG_USER": "kokonut_runtime",
            "PG_PASSWORD": "unused-shared-password",
        },
    )

    assert result is connection
    connect.assert_called_once_with(
        dsn,
        connect_timeout=8,
        application_name="kokonut-worker-remote_sensing",
    )
    cursor.execute.assert_called_once_with("SELECT current_user")


def test_remote_sensing_factory_has_no_shared_dsn_fallback(monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(worker_database.psycopg2, "connect", connect)

    with pytest.raises(
        worker_database.WorkerDatabaseConfigurationError,
        match="KOKONUT_REMOTE_SENSING_DATABASE_URL is required",
    ):
        worker_database.get_worker_db(
            "remote_sensing",
            environ={"DATABASE_URL": "postgresql://kokonut_runtime@database/kokonut_intelligence"},
        )

    connect.assert_not_called()


def test_unexpected_database_login_closes_connection_without_exposing_dsn(monkeypatch):
    connection, _ = _connection("kokonut_runtime")
    monkeypatch.setattr(worker_database.psycopg2, "connect", MagicMock(return_value=connection))
    dsn = "postgresql://secret-user:secret-password@db.invalid/private"

    with pytest.raises(
        worker_database.WorkerDatabaseConfigurationError,
        match="worker database login must be kokonut_worker_login",
    ) as error:
        worker_database.get_worker_db(
            "sensor_anomaly",
            environ={"KOKONUT_SENSOR_ANOMALY_DATABASE_URL": dsn},
        )

    assert dsn not in str(error.value)
    connection.close.assert_called_once_with()


def test_autocommit_worker_connection_is_closed_and_rejected(monkeypatch):
    connection, _ = _connection("kokonut_worker_login", autocommit=True)
    monkeypatch.setattr(worker_database.psycopg2, "connect", MagicMock(return_value=connection))

    with pytest.raises(
        worker_database.WorkerDatabaseConfigurationError,
        match="must use transactions",
    ):
        worker_database.get_worker_db(
            "sensor_anomaly",
            environ={
                "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://worker@db/kokonut"
            },
        )

    connection.cursor.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize("connect_timeout", [0, -1, True, "8"])
def test_invalid_timeout_is_rejected_before_connection(connect_timeout, monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(worker_database.psycopg2, "connect", connect)

    with pytest.raises(ValueError, match="connect_timeout"):
        worker_database.get_worker_db(
            "sensor_anomaly",
            connect_timeout=connect_timeout,
            environ={
                "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://worker@db/kokonut"
            },
        )

    connect.assert_not_called()
