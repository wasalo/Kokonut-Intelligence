"""Lazy MQTT client construction; domain validation stays with ingestion."""

from __future__ import annotations

from typing import Any


def create_client(*, client_id: str = "", clean_session: bool | None = None, manual_ack: bool = False) -> Any | None:
    """Create the existing Paho v2 callback client only when MQTT is selected.

    Disabled selection returns None. Missing driver raises ImportError so callers
    retain their existing CLI/error behavior. No broker connection is made here.
    """
    from services.core.providers import ProviderSettings

    if not ProviderSettings.from_environment().mqtt:
        return None

    import paho.mqtt.client as mqtt

    return mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=client_id,
        clean_session=clean_session, manual_ack=manual_ack,
    )
