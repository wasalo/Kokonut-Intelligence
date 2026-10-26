"""Shared SMTP delivery enforces explicit and authenticated transport modes."""

from email.message import EmailMessage
from unittest.mock import MagicMock

import pytest

from services.common import smtp


def _message() -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "Synthetic alert"
    message["From"] = "alerts@example.test"
    message["To"] = "ops@example.test"
    message.set_content("No provider call is made by this test.")
    return message


def _server(monkeypatch: pytest.MonkeyPatch, name: str = "SMTP"):
    server = MagicMock()
    server.__enter__.return_value = server
    factory = MagicMock(return_value=server)
    monkeypatch.setattr(smtp.smtplib, name, factory)
    return server, factory


def test_starttls_is_default_and_authentication_follows_tls(monkeypatch):
    server, factory = _server(monkeypatch)
    context = object()
    monkeypatch.setattr(smtp.ssl, "create_default_context", lambda: context)

    smtp.send_message(
        _message(),
        host="smtp.example.test",
        port=25,
        username="synthetic-user",
        password="synthetic-password",
    )

    factory.assert_called_once_with("smtp.example.test", 25, timeout=10)
    assert server.ehlo.call_count == 2
    server.starttls.assert_called_once_with(context=context)
    server.login.assert_called_once_with("synthetic-user", "synthetic-password")
    server.send_message.assert_called_once()


def test_implicit_tls_uses_smtp_ssl_and_verified_default_context(monkeypatch):
    server, factory = _server(monkeypatch, "SMTP_SSL")
    context = object()
    monkeypatch.setattr(smtp.ssl, "create_default_context", lambda: context)

    smtp.send_message(
        _message(),
        host="smtp.example.test",
        port=465,
        tls_mode="implicit",
    )

    factory.assert_called_once_with(
        "smtp.example.test", 465, timeout=10, context=context
    )
    server.ehlo.assert_called_once_with()
    server.starttls.assert_not_called()
    server.send_message.assert_called_once()


def test_plain_transport_requires_explicit_mode_and_disallows_auth(monkeypatch):
    server, factory = _server(monkeypatch)

    smtp.send_message(
        _message(), host="smtp.example.test", port=25, tls_mode="plain"
    )
    factory.assert_called_once_with("smtp.example.test", 25, timeout=10)
    server.starttls.assert_not_called()
    server.login.assert_not_called()

    factory.reset_mock()
    with pytest.raises(smtp.SMTPConfigurationError, match="requires a TLS"):
        smtp.send_message(
            _message(),
            host="smtp.example.test",
            port=25,
            username="synthetic-user",
            tls_mode="plain",
        )
    factory.assert_not_called()


@pytest.mark.parametrize(
    ("port", "tls_mode", "message"),
    [
        (0, "starttls", "port"),
        (65536, "starttls", "port"),
        (True, "starttls", "port"),
        (587, "disabled", "TLS mode"),
    ],
)
def test_invalid_transport_settings_fail_before_connecting(
    monkeypatch, port, tls_mode, message
):
    _server(monkeypatch)

    with pytest.raises(smtp.SMTPConfigurationError, match=message):
        smtp.send_message(
            _message(),
            host="smtp.example.test",
            port=port,
            tls_mode=tls_mode,
        )
    smtp.smtplib.SMTP.assert_not_called()


def test_empty_host_fails_before_connecting(monkeypatch):
    _server(monkeypatch)

    with pytest.raises(smtp.SMTPConfigurationError, match="host"):
        smtp.send_message(_message(), host=" ", port=587)
    smtp.smtplib.SMTP.assert_not_called()
