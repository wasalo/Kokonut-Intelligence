"""ML-based anomaly detection for sensor data.

Uses Facebook Prophet for univariate seasonal anomaly detection
and Isolation Forest for multivariate cross-sensor anomaly detection.
Falls back to rule-based detection when ML dependencies are unavailable.
Pickle artifacts are loaded only from an owner-controlled model directory
that is not group/world writable; never place uploaded or otherwise untrusted
artifacts in ``ML_MODEL_DIR``.

Usage:
    python3 -m services.ingestion.anomaly_detector --ml-check
    python3 -m services.ingestion.anomaly_detector --ml-check --sensor UUID
    python3 -m services.ingestion.anomaly_detector --ml-train --location-id UUID
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("ingestion.ml_anomaly_detector")

# Model storage directory
MODEL_DIR = Path(os.environ.get("ML_MODEL_DIR", "models/ml_anomaly"))


def _open_trusted_model_directory(create: bool = False) -> Optional[int]:
    """Open the model directory without following path-component symlinks.

    When ``create`` is true, missing components are created relative to the
    already-open parent descriptor. The returned descriptor must be closed.
    """
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory_flag = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory_flag is None:
        return None

    flags = os.O_RDONLY | directory_flag | nofollow | getattr(os, "O_CLOEXEC", 0)
    absolute_path = Path(os.path.abspath(os.fspath(MODEL_DIR)))
    if len(absolute_path.parts) <= 1:
        return None

    directory_fd = -1
    try:
        directory_fd = os.open(os.sep, flags)
        for component in absolute_path.parts[1:]:
            try:
                child_fd = os.open(component, flags, dir_fd=directory_fd)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(component, mode=0o700, dir_fd=directory_fd)
                except FileExistsError:
                    pass
                child_fd = os.open(component, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = child_fd
        info = os.fstat(directory_fd)
    except OSError:
        if directory_fd >= 0:
            os.close(directory_fd)
        return None

    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    ):
        os.close(directory_fd)
        return None
    return directory_fd


def _is_trusted_model_file(info: os.stat_result) -> bool:
    return (
        stat.S_ISREG(info.st_mode)
        and info.st_uid == os.geteuid()
        and info.st_mode & (stat.S_IWGRP | stat.S_IWOTH) == 0
    )


def _safe_model_filename(filename: str) -> bool:
    return (
        bool(filename)
        and filename not in {".", ".."}
        and os.path.basename(filename) == filename
        and "/" not in filename
        and "\\" not in filename
    )


def _open_trusted_model_file(directory_fd: int, filename: str) -> Optional[int]:
    """Open and validate one artifact using the descriptor used for loading."""
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None or not _safe_model_filename(filename):
        return None

    flags = (
        os.O_RDONLY
        | nofollow
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    file_fd = -1
    try:
        file_fd = os.open(filename, flags, dir_fd=directory_fd)
        info = os.fstat(file_fd)
    except OSError:
        if file_fd >= 0:
            os.close(file_fd)
        return None

    if not _is_trusted_model_file(info):
        os.close(file_fd)
        return None
    return file_fd


def _save_model_artifact(directory_fd: int, filename: str, model: Any) -> None:
    """Write a pickle through the trusted directory descriptor, never a path."""
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None or not _safe_model_filename(filename):
        raise OSError("Unsafe model artifact path")

    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | nofollow
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    file_fd = os.open(filename, flags, 0o600, dir_fd=directory_fd)
    try:
        if not _is_trusted_model_file(os.fstat(file_fd)):
            raise OSError("Refusing to overwrite an untrusted model artifact")
        os.fchmod(file_fd, 0o600)
        os.ftruncate(file_fd, 0)
        import pickle

        stream = os.fdopen(file_fd, "wb")
        file_fd = -1
        with stream:
            pickle.dump(model, stream)
    finally:
        if file_fd >= 0:
            os.close(file_fd)


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

    # Try loading saved models first (avoids expensive retraining)
    saved = load_models(location_id, max_age_days=7)
    prophet_cache = saved.get("prophet", {})
    iforest_cache = saved.get("iforest")

    # Prophet: per-sensor univariate detection
    for sensor in sensors:
        sensor_type = sensor["sensor_type"]
        df = _query_sensor_timeseries(conn, location_id or str(sensors[0].get("location_id")), sensor_type, lookback_days=30)

        if len(df) >= 100:
            model = prophet_cache.get(sensor_type)
            if not model:
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
            iforest_tuple = iforest_cache
            if not iforest_tuple:
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

    model_dir_fd = _open_trusted_model_directory(create=True)
    if model_dir_fd is None:
        logger.error("Refusing to save ML models to an untrusted model directory")
        return {
            "status": "error",
            "message": "Model directory must be process-owned and not group/world writable",
        }

    saved = []
    try:
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
                filename = f"prophet_{location_id[:8]}_{sensor_type}.pkl"
                try:
                    _save_model_artifact(model_dir_fd, filename, model)
                    saved.append(f"prophet_{sensor_type}")
                except Exception as e:
                    logger.error("Failed to save Prophet model for %s: %s", sensor_type, e)

        # Isolation Forest model
        iforest_tuple = fit_isolation_forest(conn, location_id, lookback_days=30)
        if iforest_tuple:
            filename = f"iforest_{location_id[:8]}.pkl"
            try:
                _save_model_artifact(model_dir_fd, filename, iforest_tuple)
                saved.append("isolation_forest")
            except Exception as e:
                logger.error("Failed to save Isolation Forest model: %s", e)

        return {"status": "success", "models_saved": saved, "model_dir": str(MODEL_DIR)}
    finally:
        os.close(model_dir_fd)


def load_models(
    location_id: str,
    max_age_days: int = 7,
) -> Dict[str, Any]:
    """Load saved ML models from disk, skipping stale or untrusted files.

    Returns:
        {"prophet": {sensor_type: model}, "iforest": (model, scaler, features)}
        Missing or stale models are omitted.
    """
    import time

    result: Dict[str, Any] = {"prophet": {}, "iforest": None}
    directory_fd = _open_trusted_model_directory()
    if directory_fd is None:
        logger.warning("Missing or untrusted ML model directory; skipping saved artifacts")
        return result

    now = time.time()
    max_age_secs = max_age_days * 86400
    try:
        filenames = set(os.listdir(directory_fd))

        # Load Prophet models
        prefix = f"prophet_{location_id[:8]}_"
        for filename in filenames:
            if not filename.startswith(prefix) or not filename.endswith(".pkl"):
                continue
            sensor_type = filename[len(prefix):-4]
            file_fd = _open_trusted_model_file(directory_fd, filename)
            if file_fd is None:
                logger.warning("Untrusted Prophet model artifact %s; skipping", filename)
                continue
            try:
                info = os.fstat(file_fd)
                if now - info.st_mtime > max_age_secs:
                    logger.info(
                        "Stale Prophet model for %s (age > %d days), skipping",
                        sensor_type,
                        max_age_days,
                    )
                    continue
                import pickle

                stream = os.fdopen(file_fd, "rb")
                file_fd = -1
                with stream:
                    result["prophet"][sensor_type] = pickle.load(stream)  # noqa: S301 - opened and validated by descriptor
            except Exception as e:
                logger.warning("Failed to load Prophet model %s: %s", filename, e)
            finally:
                if file_fd >= 0:
                    os.close(file_fd)

        # Load Isolation Forest
        iforest_filename = f"iforest_{location_id[:8]}.pkl"
        if iforest_filename in filenames:
            file_fd = _open_trusted_model_file(directory_fd, iforest_filename)
            if file_fd is None:
                logger.warning(
                    "Untrusted Isolation Forest artifact %s; skipping",
                    iforest_filename,
                )
            else:
                try:
                    info = os.fstat(file_fd)
                    if now - info.st_mtime > max_age_secs:
                        logger.info(
                            "Stale Isolation Forest model (age > %d days), skipping",
                            max_age_days,
                        )
                    else:
                        import pickle

                        stream = os.fdopen(file_fd, "rb")
                        file_fd = -1
                        with stream:
                            result["iforest"] = pickle.load(stream)  # noqa: S301 - opened and validated by descriptor
                except Exception as e:
                    logger.warning("Failed to load Isolation Forest model: %s", e)
                finally:
                    if file_fd >= 0:
                        os.close(file_fd)

        return result
    finally:
        os.close(directory_fd)
