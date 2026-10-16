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
