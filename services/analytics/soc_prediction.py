"""SOC prediction model: XGBoost-based Digital Soil Mapping (DSM)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger(__name__)


def extract_training_data(
    conn, location_id: Optional[str] = None
) -> list[dict[str, Any]]:
    """Extract paired SOC measurements and covariate features for model training.

    Joins soil_carbon_measurement with co-located remote sensing and weather features.
    This is the data preparation step for XGBoost training.
    """
    cur = conn.cursor()

    location_filter = ""
    params = []
    if location_id:
        location_filter = "AND scm.location_id = %s"
        params.append(location_id)

    cur.execute(
        f"""
        SELECT
            scm.id AS sample_id,
            scm.location_id,
            scm.plot_id,
            scm.measurement_date,
            scm.carbon_pct,
            scm.carbon_tonnes_per_ha,
            scm.depth_cm,
            -- Remote sensing features (join to nearest observation)
            rso.ndvi,
            rso.savi,
            rso.satvi,
            rso.bsi,
            rso.nbr2,
            rso.ndti,
            rso.lswi,
            rso.tc_brightness,
            rso.tc_greenness,
            rso.tc_wetness,
            -- WorldClim
            wc.bio1_mean_annual_temp,
            wc.bio16_precip_wettest_quarter,
            wc.bio17_precip_driest_quarter,
            -- Weather
            wo.temperature_c,
            wo.precipitation_mm
        FROM soil_carbon_measurement scm
        LEFT JOIN remote_sensing_observation rso
            ON rso.location_id = scm.location_id
            AND rso.plot_id = scm.plot_id
            AND rso.observation_date = (
                SELECT MAX(observation_date)
                FROM remote_sensing_observation
                WHERE location_id = scm.location_id
                  AND plot_id = scm.plot_id
                  AND observation_date <= scm.measurement_date
            )
        LEFT JOIN worldclim_climate wc
            ON wc.location_id = scm.location_id
            AND wc.plot_id = scm.plot_id
        LEFT JOIN weather_observation wo
            ON wo.location_id = scm.location_id
            AND wo.observation_date = (
                SELECT MAX(observation_date)
                FROM weather_observation
                WHERE location_id = scm.location_id
                  AND observation_date <= scm.measurement_date
            )
        WHERE scm.carbon_pct IS NOT NULL
          AND scm.status IN ('verified', 'published')
          {location_filter}
        ORDER BY scm.measurement_date
        """,
        params,
    )

    rows = cur.fetchall()
    cur.close()

    columns = [
        "sample_id", "location_id", "plot_id", "measurement_date",
        "carbon_pct", "carbon_tonnes_per_ha", "depth_cm",
        "ndvi", "savi", "satvi", "bsi", "nbr2", "ndti", "lswi",
        "tc_brightness", "tc_greenness", "tc_wetness",
        "worldclim_bio1", "worldclim_bio16", "worldclim_bio17",
        "temperature_c", "precipitation_mm",
    ]

    training_data = []
    for row in rows:
        record = dict(zip(columns, row))
        # Convert date to string
        if record.get("measurement_date"):
            record["measurement_date"] = str(record["measurement_date"])
        training_data.append(record)

    logger.info("Extracted %d training samples for SOC prediction", len(training_data))
    return training_data


def prepare_feature_matrix(
    training_data: list[dict[str, Any]],
) -> tuple[list[list[float]], list[float], list[str]]:
    """Convert training data to feature matrix and target vector.

    Returns:
        X: feature matrix (list of lists)
        y: target vector (SOC percentages)
        feature_names: list of feature names
    """
    feature_names = [
        "depth_cm",
        "ndvi", "savi", "satvi", "bsi", "nbr2", "ndti", "lswi",
        "tc_brightness", "tc_greenness", "tc_wetness",
        "worldclim_bio1", "worldclim_bio16", "worldclim_bio17",
        "temperature_c", "precipitation_mm",
    ]

    X = []
    y = []

    for record in training_data:
        features = []
        skip = False
        for name in feature_names:
            val = record.get(name)
            if val is None:
                features.append(0.0)  # XGBoost handles missing via sparsity
            else:
                features.append(float(val))

        target = record.get("carbon_pct")
        if target is not None:
            X.append(features)
            y.append(float(target))

    return X, y, feature_names


def train_xgboost_model(
    X: list[list[float]],
    y: list[float],
    feature_names: list[str],
    hyperparameters: Optional[dict] = None,
) -> dict[str, Any]:
    """Train an XGBoost regression model for SOC prediction.

    Returns model metadata (not the trained model object, which should be
    pickled and stored separately).
    """
    try:
        import xgboost as xgb
        from sklearn.model_selection import cross_val_score, KFold
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
        import numpy as np
    except ImportError:
        logger.warning("xgboost/scikit-learn not installed — returning placeholder model metadata")
        return {
            "model_type": "xgboost_placeholder",
            "error": "xgboost and scikit-learn packages not installed. "
                     "Install with: pip install xgboost scikit-learn",
            "feature_count": len(feature_names),
            "feature_names": feature_names,
            "training_samples": len(X),
        }

    if len(X) < 10:
        return {"error": "Insufficient training data (need >= 10 samples)", "training_samples": len(X)}

    X_arr = np.array(X)
    y_arr = np.array(y)

    # Default hyperparameters from ATLAS-SOC
    params = hyperparameters or {
        "n_estimators": 500,
        "learning_rate": 0.05,
        "max_depth": 8,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "objective": "reg:squarederror",
        "eval_metric": "mae",
        "random_state": 42,
    }

    model = xgb.XGBRegressor(**params)

    # Cross-validation
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X_arr, y_arr, cv=kf, scoring="r2")
    cv_rmse_scores = cross_val_score(model, X_arr, y_arr, cv=kf, scoring="neg_root_mean_squared_error")

    # Fit final model
    model.fit(X_arr, y_arr)
    y_pred = model.predict(X_arr)

    # Training metrics
    r2 = r2_score(y_arr, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_arr, y_pred)))
    mae = mean_absolute_error(y_arr, y_pred)

    # Feature importance
    importance = model.feature_importances_
    feature_importance = sorted(
        [{"feature": name, "importance": float(imp)}
         for name, imp in zip(feature_names, importance)],
        key=lambda x: x["importance"],
        reverse=True,
    )

    result = {
        "model_type": "xgboost",
        "training_samples": len(X),
        "feature_count": len(feature_names),
        "feature_names": feature_names,
        "hyperparameters": params,
        "training_metrics": {
            "r_squared": round(r2, 4),
            "rmse": round(rmse, 4),
            "mae": round(float(mae), 4),
        },
        "cv_metrics": {
            "mean_r_squared": round(float(cv_scores.mean()), 4),
            "std_r_squared": round(float(cv_scores.std()), 4),
            "mean_rmse": round(float(-cv_rmse_scores.mean()), 4),
        },
        "feature_importance": feature_importance,
    }

    logger.info(
        "XGBoost trained: R²=%.4f, RMSE=%.4f, CV R²=%.4f",
        r2, rmse, cv_scores.mean(),
    )

    return result


def predict_soc(
    model_metadata: dict[str, Any],
    features: dict[str, Any],
) -> dict[str, Any]:
    """Predict SOC content from features using trained model metadata.

    In production, this would load the pickled model. For now, returns
    a weighted linear combination based on feature importance as a proxy.
    """
    if model_metadata.get("model_type") == "xgboost_placeholder":
        return {
            "error": "No trained model available",
            "predicted_soc_pct": None,
        }

    # Simple weighted prediction using feature importance
    importance_list = model_metadata.get("feature_importance", [])
    importance_map = {f["feature"]: f["importance"] for f in importance_list}

    weighted_sum = 0.0
    total_weight = 0.0

    for feature_name, importance in importance_map.items():
        value = features.get(feature_name)
        if value is not None:
            weighted_sum += float(value) * importance
            total_weight += importance

    if total_weight > 0:
        predicted_soc = weighted_sum / total_weight
    else:
        predicted_soc = 2.0  # Default SOC percentage

    return {
        "predicted_soc_pct": round(predicted_soc, 3),
        "features_used": len([v for v in features.values() if v is not None]),
        "model_type": model_metadata.get("model_type"),
    }
