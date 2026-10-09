"""Ecocredit module parameters."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.params")


def get_params(conn) -> dict:
    result = conn.execute(
        conn.text("SELECT * FROM ecocredit_params ORDER BY param_key")
    ).mappings().all()
    params = {}
    for r in result:
        params[r["param_key"]] = r["param_value"]
    return params


def get_param(conn, param_key: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM ecocredit_params WHERE param_key = :key"),
        {"key": param_key},
    ).mappings().first()
    return dict(result) if result else None


def set_param(conn, param_key: str, param_value: Any, description: str = None) -> dict:
    value = json.dumps(param_value) if isinstance(param_value, (dict, list)) else param_value
    conn.execute(
        conn.text(
            "INSERT INTO ecocredit_params (param_key, param_value, description) "
            "VALUES (:key, :val, :desc) "
            "ON CONFLICT (param_key) DO UPDATE SET "
            "param_value = EXCLUDED.param_value, description = EXCLUDED.description, "
            "updated_at = NOW()"
        ),
        {"key": param_key, "val": value, "desc": description},
    )
    return {"param_key": param_key, "param_value": param_value}


def get_class_fee(conn) -> dict:
    result = get_param(conn, "class_fee")
    return result["param_value"] if result else {"denom": "cusd", "amount": 0}


def get_basket_fee(conn) -> dict:
    result = get_param(conn, "basket_fee")
    return result["param_value"] if result else {"denom": "cusd", "amount": 0}


def get_allowed_bridge_chains(conn) -> list[str]:
    result = get_param(conn, "allowed_bridge_chains")
    if result and isinstance(result["param_value"], list):
        return result["param_value"]
    return ["celo", "gnosis"]
