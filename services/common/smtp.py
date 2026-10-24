"""Small, dependency-free SMTP transport shared by alert delivery paths."""

from __future__ import annotations

import smtplib
import ssl
from email.message import Message

TLS_MODES = frozenset({"starttls", "implicit", "plain"})


class SMTPConfigurationError(ValueError):
    """Raised when SMTP transport settings are invalid or unsafe."""


def validate_settings(
    *,
    host: str,
    port: int,
    username: str = "",
    password: str = "",
    tls_mode: str = "starttls",
) -> str:
    """Validate transport settings and return the normalized TLS mode."""
    if not isinstance(host, str) or not host.strip():
        raise SMTPConfigurationError("SMTP host is required")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise SMTPConfigurationError("SMTP port must be between 1 and 65535")
    if not isinstance(tls_mode, str):
        raise SMTPConfigurationError("SMTP TLS mode must be starttls, implicit, or plain")
    tls_mode = tls_mode.strip().lower()
    if tls_mode not in TLS_MODES:
        raise SMTPConfigurationError("SMTP TLS mode must be starttls, implicit, or plain")
    if tls_mode == "plain" and (username or password):
        raise SMTPConfigurationError("SMTP authentication requires a TLS transport")
    return tls_mode


def send_message(
    message: Message,
    *,
    host: str,
    port: int,
    username: str = "",
    password: str = "",
    tls_mode: str = "starttls",
    timeout: float = 10,
) -> None:
    """Send one message using explicit STARTTLS, implicit TLS, or plain SMTP.

    TLS is required by default. Plain transport is an explicit opt-in and may
    never carry SMTP authentication credentials.
    """
    tls_mode = validate_settings(
        host=host,
        port=port,
        username=username,
        password=password,
        tls_mode=tls_mode,
    )

    context = ssl.create_default_context()
    if tls_mode == "implicit":
        client = smtplib.SMTP_SSL(host.strip(), port, timeout=timeout, context=context)
    else:
        client = smtplib.SMTP(host.strip(), port, timeout=timeout)

    with client as server:
        server.ehlo()
        if tls_mode == "starttls":
            server.starttls(context=context)
            server.ehlo()
        if username:
            server.login(username, password)
        server.send_message(message)
