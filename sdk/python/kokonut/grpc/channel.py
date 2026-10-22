"""Optional secure gRPC channel factory for the generated SDK stubs."""

from __future__ import annotations

import ipaddress
from typing import Optional


def _is_loopback_target(target: str) -> bool:
    value = target.strip()
    for prefix in ("dns:///", "ipv4:", "ipv6:"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    host = value.rsplit(":", 1)[0] if ":" in value else value
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def create_channel(
    target: str,
    *,
    root_certificates: Optional[bytes] = None,
    allow_insecure: bool = False,
):
    """Create a gRPC channel with TLS for remote targets by default.

    ``grpcio`` is imported only when this function is called, so importing the
    base Python SDK remains independent of the optional gRPC extra. A supplied
    CA bundle enables TLS with a private trust root; plaintext for a remote
    target requires the explicit ``allow_insecure`` option.
    """
    if not isinstance(target, str) or not target.strip():
        raise ValueError("gRPC target must be a non-empty string")
    if not isinstance(allow_insecure, bool):
        raise ValueError("allow_insecure must be a boolean")
    if root_certificates is not None and not isinstance(root_certificates, bytes):
        raise ValueError("root_certificates must be bytes")
    if root_certificates is not None and not root_certificates:
        raise ValueError("root_certificates must not be empty")
    if allow_insecure and root_certificates is not None:
        raise ValueError("root_certificates cannot be combined with allow_insecure")

    import grpc

    if allow_insecure:
        return grpc.insecure_channel(target)
    if root_certificates is not None or not _is_loopback_target(target):
        credentials = grpc.ssl_channel_credentials(root_certificates=root_certificates)
        return grpc.secure_channel(target, credentials)
    return grpc.insecure_channel(target)
