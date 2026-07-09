"""ML-based anomaly detection for sensor data.

Uses Facebook Prophet for univariate seasonal anomaly detection
and Isolation Forest for multivariate cross-sensor anomaly detection.
Falls back to rule-based detection when ML dependencies are unavailable.

Usage:
    python3 -m services.ingestion.anomaly_detector --ml-check
    python3 -m services.ingestion.anomaly_detector --ml-check --sensor UUID
    python3 -m services.ingestion.anomaly_detector --ml-train --location-id UUID
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..common.logging import get_logger

logger = get_logger("ingestion.ml_anomaly_detector")

# Model storage directory
MODEL_DIR = Path(os.environ.get("ML_MODEL_DIR", "models/ml_anomaly"))

# Lazy imports for ML dependencies
_pd = None
_np = None
_prophet = None
_iforest = None


def _ensure_deps():
    """Lazily import ML dependencies with graceful fallback."""
    global _pd, _np, _prophet, _iforest

    if _pd is None:
        try:
            import pandas as pd
            _pd = pd
        except ImportError:
            logger.warning("pandas not installed. ML anomaly detection unavailable.")
            return False

    if _np is None:
        try:
            import numpy as np
            _np = np
        except ImportError:
            logger.warning("numpy not installed. ML anomaly detection unavailable.")
            return False

    if _prophet is None:
        try:
            from prophet import Prophet
            _prophet = Prophet
        except ImportError:
            logger.warning("prophet not installed. Univariate ML detection unavailable.")

    if _iforest is None:
        try:
            from sklearn.ensemble import IsolationForest
            from sklearn.preprocessing import StandardScaler
            _iforest = (IsolationForest, StandardScaler)
        except ImportError:
            logger.warning("scikit-learn not installed. Multivariate ML detection unavailable.")

    return True


def _query_sensor_timeseries(
    conn,
    location_id: str,
    sensor_type: str,
    lookback_days: int = 90,
) -> _pd.DataFrame:
    """Query sensor readings as a pandas DataFrame."""
    if _pd is None:
        return _pd.DataFrame()

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            reading_date + COALESCE(reading_time, '00:00:00') AS timestamp,
            value,
            sensor_type,
            sensor_id
        FROM sensor_reading
        WHERE location_id = %s
        AND sensor_type = %s
        AND quality IN ('good', 'estimated')
        AND reading_date >= CURRENT_DATE - INTERVAL '%s days'
        ORDER BY reading_date, reading_time
    """, (location_id, sensor_type, lookback_days))
    rows = cur.fetchall()
    cur.close()

    if not rows:
        return _pd.DataFrame()

    df = _pd.DataFrame(rows)
    df["timestamp"] = _pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    return df


def _query_all_sensors_timeseries(
    conn,
    location_id: str,
    lookback_days: int = 30,
) -> _pd.DataFrame:
    """Query all sensor types as a multi-column DataFrame."""
    if _pd is None:
        return _pd.DataFrame()

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            reading_date + COALESCE(reading_time, '00:00:00') AS timestamp,
            value,
            sensor_type
        FROM sensor_reading
        WHERE location_id = %s
        AND quality IN ('good', 'estimated')
        AND reading_date >= CURRENT_DATE - INTERVAL '%s days'
        ORDER BY reading_date, reading_time
    """, (location_id, lookback_days))
    rows = cur.fetchall()
    cur.close()

    if not rows:
        return _pd.DataFrame()

    df = _pd.DataFrame(rows)
    df["timestamp"] = _pd.to_datetime(df["timestamp"])
    df = df.pivot_table(index="timestamp", columns="sensor_type", values="value")
    df = df.sort_index()
    return df


def _build_prophet_features(df: _pd.DataFrame, sensor_type: str) -> _pd.DataFrame:
    """Prepare DataFrame for Prophet (ds, y columns)."""
    prophet_df = _pd.DataFrame({
        "ds": df.index,
        "y": df["value"].values,
    })
    return prophet_df


def fit_prophet(
    conn,
    location_id: str,
    sensor_type: str,
    lookback_days: int = 90,
) -> Optional[Any]:
    """Fit a Prophet model for a sensor type at a location.

    Returns fitted model or None if insufficient data.
    """
    if not _ensure_deps() or _prophet is None:
        return None

    df = _query_sensor_timeseries(conn, location_id, sensor_type, lookback_days)
    if len(df) < 100:  # Need at least ~4 days hourly
        logger.info("Insufficient data for Prophet (%d points, need 100+)", len(df))
        return None

    prophet_df = _build_prophet_features(df, sensor_type)

    model = _prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,  # Need 2+ years for yearly
        changepoint_prior_scale=0.05,
        interval_width=0.95,
    )

    try:
        model.fit(prophet_df)
        return model
    except Exception as e:
        logger.error("Prophet fit failed for %s: %s", sensor_type, e)
        return None


def predict_anomalies_prophet(
    model,
    df: _pd.DataFrame,
    sensor_type: str,
) -> List[Dict[str, Any]]:
    """Use fitted Prophet model to detect anomalies.

    Returns list of anomalous timestamps with actual/predicted values.
    """
    if _pd is None or model is None:
        return []

    prophet_df = _build_prophet_features(df, sensor_type)
    forecast = model.predict(prophet_df)

    # Merge actual vs predicted
    result_df = _pd.DataFrame({
        "timestamp": prophet_df["ds"].values,
        "actual": prophet_df["y"].values,
        "predicted": forecast["yhat"].values,
        "lower": forecast["yhat_lower"].values,
        "upper": forecast["yhat_upper"].values,
    })

    # Flag anomalies: actual outside prediction interval
    result_df["is_anomaly"] = (
        (result_df["actual"] < result_df["lower"]) |
        (result_df["actual"] > result_df["upper"])
    )
    result_df["anomaly_score"] = _np.abs(
        result_df["actual"] - result_df["predicted"]
    ) / (result_df["upper"] - result_df["lower"] + 1e-10)

    anomalies = result_df[result_df["is_anomaly"]].to_dict("records")
    return [
        {
            "timestamp": str(row["timestamp"]),
            "actual": round(float(row["actual"]), 4),
            "predicted": round(float(row["predicted"]), 4),
            "lower": round(float(row["lower"]), 4),
            "upper": round(float(row["upper"]), 4),
            "anomaly_score": round(float(row["anomaly_score"]), 4),
            "detection_method": "ml_prophet",
            "sensor_type": sensor_type,
        }
        for row in anomalies
    ]


def fit_isolation_forest(
    conn,
    location_id: str,
    lookback_days: int = 30,
    contamination: float = 0.05,
) -> Optional[Tuple[Any, Any]]:
    """Fit Isolation Forest on multi-sensor features.

    Returns (model, scaler) tuple or None.
    """
    if not _ensure_deps() or _iforest is None:
        return None

    IsolationForest, StandardScaler = _iforest

    df = _query_all_sensors_timeseries(conn, location_id, lookback_days)
    if df.empty or len(df) < 50:
        logger.info("Insufficient multi-sensor data for Isolation Forest")
        return None

    # Add time features
    df["hour"] = df.index.hour
    df["day_of_year"] = df.index.dayofyear

    # Add lagged features (1-hour lag)
    for col in df.columns:
        if col not in ("hour", "day_of_year"):
            df[f"{col}_lag1"] = df[col].shift(1)

    df = df.dropna()

    if len(df) < 50:
        return None

    features = df.select_dtypes(include=["number"]).columns.tolist()
    X = df[features].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
    )
    model.fit(X_scaled)

    return (model, scaler)


def score_anomalies_iforest(
    model_tuple,
    df: _pd.DataFrame,
) -> List[Dict[str, Any]]:
    """Score anomalies using fitted Isolation Forest."""
    if _pd is None or _np is None or model_tuple is None:
        return []

    model, scaler = model_tuple

    # Add time features
    df = df.copy()
    df["hour"] = df.index.hour
    df["day_of_year"] = df.index.dayofyear

    # Add lagged features
    for col in df.columns:
        if col not in ("hour", "day_of_year"):
            df[f"{col}_lag1"] = df[col].shift(1)

    df = df.dropna()

    if df.empty:
        return []

    features = df.select_dtypes(include=["number"]).columns.tolist()
    X = df[features].values
    X_scaled = scaler.transform(X)

    scores = model.score_samples(X_scaled)
    predictions = model.predict(X_scaled)

    anomalies = []
    for i, (ts, pred, score) in enumerate(zip(df.index, predictions, scores)):
        if pred == -1:  # Anomaly
            anomalies.append({
                "timestamp": str(ts),
                "anomaly_score": round(float(-score), 4),
                "detection_method": "ml_isolation_forest",
                "features": {f: round(float(X[i][j]), 4) for j, f in enumerate(features) if "_lag" not in f},
            })

    return anomalies


def run_ml_check(
    conn,
    location_id: str = None,
    sensor_id: str = None,
) -> Dict[str, Any]:
    """Run ML anomaly detection for a location or specific sensor.

    Returns summary of detected anomalies.
    """
    if not _ensure_deps():
        return {"status": "error", "message": "ML dependencies not available", "anomalies": []}

    # Get sensors to check
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = """
        SELECT DISTINCT sr.sensor_type, sr.sensor_id, sd.slug AS device_slug
        FROM sensor_reading sr
        JOIN sensor_device sd ON sd.id = sr.sensor_id
        WHERE sr.quality IN ('good', 'estimated')
        AND sr.reading_date >= CURRENT_DATE - INTERVAL '7 days'
    """
    params = []
    if location_id:
        query += " AND sr.location_id = %s"
        params.append(location_id)
    if sensor_id:
        query += " AND sr.sensor_id = %s"
        params.append(sensor_id)
    cur.execute(query, params)
    sensors = [dict(r) for r in cur.fetchall()]
    cur.close()

    all_anomalies = []

    # Prophet: per-sensor univariate detection
    for sensor in sensors:
        sensor_type = sensor["sensor_type"]
        df = _query_sensor_timeseries(conn, location_id or str(sensors[0].get("location_id")), sensor_type, lookback_days=30)

        if len(df) >= 100:
            model = fit_prophet(conn, location_id, sensor_type, lookback_days=90)
            if model:
                anomalies = predict_anomalies_prophet(model, df, sensor_type)
                for a in anomalies:
                    a["device_slug"] = sensor["device_slug"]
                all_anomalies.extend(anomalies)

    # Isolation Forest: multivariate detection
    if location_id:
        all_sensors_df = _query_all_sensors_timeseries(conn, location_id, lookback_days=30)
        if not all_sensors_df.empty and len(all_sensors_df) >= 50:
            iforest_tuple = fit_isolation_forest(conn, location_id, lookback_days=30)
            if iforest_tuple:
                if_anomalies = score_anomalies_iforest(iforest_tuple, all_sensors_df)
                for a in if_anomalies:
                    a["device_slug"] = "multivariate"
                all_anomalies.extend(if_anomalies)

    # Deduplicate by timestamp + method
    seen = set()
    unique_anomalies = []
    for a in all_anomalies:
        key = (a["timestamp"], a["detection_method"])
        if key not in seen:
            seen.add(key)
            unique_anomalies.append(a)

    return {
        "status": "success",
        "location_id": location_id,
        "sensors_checked": len(sensors),
        "anomalies_detected": len(unique_anomalies),
        "anomalies": unique_anomalies,
    }


def save_models(conn, location_id: str) -> Dict[str, Any]:
    """Fit and save ML models for a location."""
    if not _ensure_deps():
        return {"status": "error", "message": "ML dependencies not available"}

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    saved = []
    # Prophet models per sensor type
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT DISTINCT sensor_type FROM sensor_reading
        WHERE location_id = %s AND quality IN ('good', 'estimated')
    """, (location_id,))
    sensor_types = [r["sensor_type"] for r in cur.fetchall()]
    cur.close()

    for sensor_type in sensor_types:
        model = fit_prophet(conn, location_id, sensor_type, lookback_days=90)
        if model:
            model_path = MODEL_DIR / f"prophet_{location_id[:8]}_{sensor_type}.pkl"
            try:
                import pickle
                with open(model_path, "wb") as f:
                    pickle.dump(model, f)
                saved.append(f"prophet_{sensor_type}")
            except Exception as e:
                logger.error("Failed to save Prophet model for %s: %s", sensor_type, e)

    # Isolation Forest model
    iforest_tuple = fit_isolation_forest(conn, location_id, lookback_days=30)
    if iforest_tuple:
        model_path = MODEL_DIR / f"iforest_{location_id[:8]}.pkl"
        try:
            import pickle
            with open(model_path, "wb") as f:
                pickle.dump(iforest_tuple, f)
            saved.append("isolation_forest")
        except Exception as e:
            logger.error("Failed to save Isolation Forest model: %s", e)

    return {"status": "success", "models_saved": saved, "model_dir": str(MODEL_DIR)}
