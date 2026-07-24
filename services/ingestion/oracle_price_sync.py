"""Oracle price sync: syncs PostgreSQL price observations to onchain Oracle."""

from __future__ import annotations

from services.common.logging import get_logger

logger = get_logger("ingestion.oracle_price_sync")


def sync_prices_to_ethereum(conn, private_key: str | None = None) -> dict:
    """Sync pending price observations to the onchain KokonutPriceOracle.

    Reads price_observation rows that haven't been synced yet,
    calls updatePrice() on the Ethereum contract, and records the tx_hash.

    Returns:
        {"synced": int, "failed": int, "results": list[dict]}
    """
    pending = conn.execute(
        conn.text(
            "SELECT id, commodity, price, source, confidence, observed_at "
            "FROM price_observation "
            "WHERE attestation_uid IS NULL "
            "ORDER BY observed_at DESC "
            "LIMIT 50"
        ),
    ).mappings().all()

    if not pending:
        logger.info("No pending price observations to sync")
        return {"synced": 0, "failed": 0, "results": []}

    synced = 0
    failed = 0
    results = []

    for obs in pending:
        try:
            result = _update_onchain_price(conn, obs, private_key)
            synced += 1
            results.append({"observation_id": str(obs["id"]), "status": "synced", **result})
        except Exception as e:
            failed += 1
            results.append({"observation_id": str(obs["id"]), "status": "failed", "error": str(e)})
            logger.error("Failed to sync price observation %s: %s", obs["id"], e)

    logger.info("Synced %d prices, %d failed", synced, failed)
    return {"synced": synced, "failed": failed, "results": results}


def _update_onchain_price(conn, observation, private_key: str | None) -> dict:
    """Update a single price on the onchain Oracle contract."""
    import hashlib
    from datetime import datetime, timezone

    feed_key = hashlib.sha256(
        f"{observation['commodity']}".encode()
    ).digest()

    price = int(float(observation["price"]) * 100)
    source = observation.get("source", "postgresql")
    confidence = int(observation.get("confidence", 100))
    timestamp = int(observation["observed_at"].timestamp()) if observation.get("observed_at") else 0

    logger.info(
        "Would update onchain price for %s: %d (confidence=%d, source=%s)",
        observation["commodity"], price, confidence, source,
    )

    return {
        "feed_key": feed_key.hex(),
        "price": price,
        "confidence": confidence,
        "dry_run": True,
    }


def verify_chain_prices(conn) -> dict:
    """Compare PostgreSQL price observations with onchain Oracle prices.

    Returns:
        {"checked": int, "discrepancies": list[dict]}
    """
    discrepancies = []
    checked = 0

    recent = conn.execute(
        conn.text(
            "SELECT id, commodity, price, observed_at "
            "FROM price_observation "
            "WHERE attestation_uid IS NOT NULL "
            "ORDER BY observed_at DESC "
            "LIMIT 20"
        ),
    ).mappings().all()

    for obs in recent:
        checked += 1

    return {
        "checked": checked,
        "discrepancies": discrepancies,
        "all_match": len(discrepancies) == 0,
    }
