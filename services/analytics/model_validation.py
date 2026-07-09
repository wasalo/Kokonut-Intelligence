"""Validation framework: geographic cross-validation, field-level metrics, MEC computation."""

from __future__ import annotations

import math
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_rmse(predicted: list[float], actual: list[float]) -> float:
    """Compute Root Mean Squared Error."""
    if len(predicted) != len(actual) or len(predicted) == 0:
        return 0.0
    n = len(predicted)
    sse = sum((p - a) ** 2 for p, a in zip(predicted, actual))
    return math.sqrt(sse / n)


def compute_mae(predicted: list[float], actual: list[float]) -> float:
    """Compute Mean Absolute Error."""
    if len(predicted) != len(actual) or len(predicted) == 0:
        return 0.0
    return sum(abs(p - a) for p, a in zip(predicted, actual)) / len(predicted)


def compute_me(predicted: list[float], actual: list[float]) -> float:
    """Compute Mean Error (bias)."""
    if len(predicted) != len(actual) or len(predicted) == 0:
        return 0.0
    return sum(p - a for p, a in zip(predicted, actual)) / len(predicted)


def compute_r_squared(predicted: list[float], actual: list[float]) -> float:
    """Compute coefficient of determination (R²)."""
    if len(predicted) != len(actual) or len(predicted) == 0:
        return 0.0
    mean_actual = sum(actual) / len(actual)
    ss_res = sum((a - p) ** 2 for a, p in zip(actual, predicted))
    ss_tot = sum((a - mean_actual) ** 2 for a in actual)
    if ss_tot == 0:
        return 0.0
    return 1.0 - (ss_res / ss_tot)


def compute_mec(predicted: list[float], actual: list[float]) -> float:
    """Compute Modeling Efficiency Coefficient (MEC / Nash-Sutcliffe).

    MEC = 1 - SS_residual / SS_total
    MEC = 1.0 is perfect, MEC <= 0 means model is worse than using the mean.
    """
    if len(predicted) != len(actual) or len(predicted) == 0:
        return 0.0
    mean_actual = sum(actual) / len(actual)
    ss_res = sum((a - p) ** 2 for a, p in zip(actual, predicted))
    ss_tot = sum((a - mean_actual) ** 2 for a in actual)
    if ss_tot == 0:
        return 0.0
    return 1.0 - (ss_res / ss_tot)


def compute_regression_metrics(
    predicted: list[float], actual: list[float]
) -> dict[str, Any]:
    """Compute all regression metrics for SOC prediction evaluation."""
    if not predicted or not actual:
        return {
            "r_squared": 0.0,
            "rmse": 0.0,
            "mae": 0.0,
            "me": 0.0,
            "mec": 0.0,
            "intercept": 0.0,
            "slope": 1.0,
            "n": 0,
        }

    r2 = compute_r_squared(predicted, actual)
    rmse = compute_rmse(predicted, actual)
    mae = compute_mae(predicted, actual)
    me = compute_me(predicted, actual)
    mec = compute_mec(predicted, actual)

    # Linear regression: actual = intercept + slope * predicted
    n = len(predicted)
    mean_pred = sum(predicted) / n
    mean_act = sum(actual) / n
    ss_xy = sum((p - mean_pred) * (a - mean_act) for p, a in zip(predicted, actual))
    ss_xx = sum((p - mean_pred) ** 2 for p in predicted)

    slope = ss_xy / ss_xx if ss_xx != 0 else 1.0
    intercept = mean_act - slope * mean_pred

    return {
        "r_squared": round(r2, 4),
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "me": round(me, 4),
        "mec": round(mec, 4),
        "intercept": round(intercept, 4),
        "slope": round(slope, 4),
        "n": n,
    }


def geographic_cross_validation(
    training_data: list[dict[str, Any]],
    field_id_key: str = "plot_id",
    n_folds: int = 5,
) -> list[dict[str, Any]]:
    """Perform geographic cross-validation (leave-one-field-out or grouped).

    Splits data by field (plot) to ensure no spatial autocorrelation
    between training and validation sets.
    """
    # Group by field
    fields: dict[str, list[dict]] = {}
    for record in training_data:
        field_id = str(record.get(field_id_key, "unknown"))
        fields.setdefault(field_id, []).append(record)

    field_ids = list(fields.keys())
    if len(field_ids) < n_folds:
        n_folds = len(field_ids)

    if n_folds <= 0:
        return []

    # Assign fields to folds (roughly equal sizes)
    import random
    random.shuffle(field_ids)
    folds = [[] for _ in range(n_folds)]
    for i, field_id in enumerate(field_ids):
        folds[i % n_folds].append(field_id)

    cv_results = []
    for fold_idx in range(n_folds):
        test_field_ids = folds[fold_idx]
        train_field_ids = [fid for fid in field_ids if fid not in test_field_ids]

        train_data = [r for fid in train_field_ids for r in fields[fid]]
        test_data = [r for fid in test_field_ids for r in fields[fid]]

        if not test_data:
            continue

        cv_results.append({
            "fold": fold_idx + 1,
            "train_samples": len(train_data),
            "test_samples": len(test_data),
            "excluded_fields": test_field_ids,
            "train_fields": len(train_field_ids),
            "test_fields": len(test_field_ids),
        })

    return cv_results


def aggregate_to_field_level(
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate pixel-level predictions to field-level means.

    Groups predictions by plot_id and computes mean predicted and measured SOC.
    """
    fields: dict[str, dict] = {}

    for pred in predictions:
        field_id = str(pred.get("plot_id", "unknown"))
        if field_id not in fields:
            fields[field_id] = {
                "plot_id": field_id,
                "predicted_values": [],
                "measured_values": [],
                "location_id": pred.get("location_id"),
            }
        if pred.get("predicted_soc_pct") is not None:
            fields[field_id]["predicted_values"].append(float(pred["predicted_soc_pct"]))
        if pred.get("measured_soc_pct") is not None:
            fields[field_id]["measured_values"].append(float(pred["measured_soc_pct"]))

    field_results = []
    for field_id, data in fields.items():
        if data["predicted_values"] and data["measured_values"]:
            mean_pred = sum(data["predicted_values"]) / len(data["predicted_values"])
            mean_meas = sum(data["measured_values"]) / len(data["measured_values"])
            field_results.append({
                "plot_id": field_id,
                "location_id": data["location_id"],
                "mean_predicted_soc": round(mean_pred, 3),
                "mean_measured_soc": round(mean_meas, 3),
                "sample_count": len(data["predicted_values"]),
            })

    return field_results
