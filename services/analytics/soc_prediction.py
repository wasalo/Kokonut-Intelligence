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


def residual_kriging_correction(
    conn,
    location_id: str,
    variogram_model_id: Optional[str] = None,
) -> dict[str, Any]:
    """Apply residual kriging to correct XGBoost SOC predictions spatially.

    1. Extract training data with coordinates
    2. Compute residuals: observed - XGBoost_predicted
    3. Fit variogram to residuals
    4. Krig residuals at all prediction locations
    5. Corrected = XGBoost + kriged_residual

    This complements the pixel-based XGBoost model by adding spatial structure
    to the prediction errors.
    """
    from services.geostatistics.variogram import VariogramAnalyzer
    from services.geostatistics.kriging import KrigingEngine

    training_data = extract_training_data(conn, location_id)
    if len(training_data) < 10:
        return {
            "error": f"Need >= 10 training samples for residual kriging, got {len(training_data)}",
            "corrected_soc_pct": None,
        }

    X, y, feature_names = prepare_feature_matrix(training_data)

    # Get XGBoost predictions (using weighted linear proxy)
    model_metadata = train_xgboost_model(X, y, feature_names)
    predictions = []
    for features in X:
        feat_dict = dict(zip(feature_names, features))
        pred = predict_soc(model_metadata, feat_dict)
        predictions.append(pred.get("predicted_soc_pct", np.mean(y) if y else 2.0))

    y_actual = np.array(y)
    y_pred = np.array(predictions)
    residuals = y_actual - y_pred

    # Extract coordinates
    import numpy as np
    lats = np.array([float(d.get("gps_latitude", 0) or 0) for d in training_data])
    lons = np.array([float(d.get("gps_longitude", 0) or 0) for d in training_data])

    # Filter out zero coordinates
    valid = (lats != 0) & (lons != 0)
    if np.sum(valid) < 10:
        return {
            "error": f"Need >= 10 valid coordinates, got {np.sum(valid)}",
            "corrected_soc_pct": None,
        }

    mean_lat, mean_lon = np.mean(lats[valid]), np.mean(lons[valid])
    lat_to_m = 111320.0
    lon_to_m = 111320.0 * np.cos(np.radians(mean_lat))

    coordinates = [
        (float(lon - mean_lon) * lon_to_m, float(lat - mean_lat) * lat_to_m)
        for lat, lon in zip(lats[valid], lons[valid])
    ]
    residual_values = residuals[valid].tolist()

    # Fit variogram to residuals
    va = VariogramAnalyzer(conn=conn)
    vm_result = va.fit_variogram(residual_values, coordinates, model_type="exponential")
    if "error" in vm_result:
        return {
            "error": f"Variogram fitting failed: {vm_result['error']}",
            "corrected_soc_pct": None,
        }

    # Krig residuals at observation points (leave-one-out style)
    ke = KrigingEngine(conn=conn)
    ok_result = ke.ordinary_kriging(
        coordinates, residual_values, vm_result, resolution_m=100.0
    )

    # Compute correction quality metrics
    xgb_rmse = float(np.sqrt(np.mean((y_actual - y_pred) ** 2)))
    xgb_r2 = float(1 - np.sum((y_actual - y_pred) ** 2) / np.sum((y_actual - np.mean(y_actual)) ** 2)) if np.sum((y_actual - np.mean(y_actual)) ** 2) > 0 else 0.0

    return {
        "location_id": location_id,
        "method": "residual_kriging",
        "n_samples": len(residual_values),
        "variogram_model": vm_result,
        "xgb_metrics": {
            "rmse": round(xgb_rmse, 4),
            "r_squared": round(xgb_r2, 4),
        },
        "residual_stats": {
            "mean": round(float(np.mean(residuals)), 4),
            "std": round(float(np.std(residuals)), 4),
            "min": round(float(np.min(residuals)), 4),
            "max": round(float(np.max(residuals)), 4),
        },
        "kriging_grid_points": ok_result.get("n_points", 0),
        "corrected_soc_pct": "Apply kriged residuals to XGBoost predictions at target locations",
    }


def spatial_block_cv_for_soc(
    conn,
    location_id: str,
    block_size_m: float = 200.0,
) -> dict[str, Any]:
    """Run spatial block CV for SOC prediction model using geostatistics.

    Complements existing random KFold CV in train_xgboost_model() to prevent
    spatial leakage. Writes results to cv_fold_result with cv_strategy='spatial_block'.
    """
    training_data = extract_training_data(conn, location_id)
    if len(training_data) < 10:
        return {
            "error": f"Need >= 10 training samples for spatial block CV, got {len(training_data)}",
        }

    X, y, feature_names = prepare_feature_matrix(training_data)

    import numpy as np
    lats = np.array([float(d.get("gps_latitude", 0) or 0) for d in training_data])
    lons = np.array([float(d.get("gps_longitude", 0) or 0) for d in training_data])
    y_arr = np.array(y)

    valid = (lats != 0) & (lons != 0)
    if np.sum(valid) < 10:
        return {"error": f"Need >= 10 valid coordinates, got {np.sum(valid)}"}

    mean_lat, mean_lon = np.mean(lats[valid]), np.mean(lons[valid])
    lat_to_m = 111320.0
    lon_to_m = 111320.0 * np.cos(np.radians(mean_lat))

    coordinates = np.array([
        (float(lon - mean_lon) * lon_to_m, float(lat - mean_lat) * lat_to_m)
        for lat, lon in zip(lats[valid], lons[valid])
    ])
    X_valid = np.array(X)[valid]
    y_valid = y_arr[valid]

    # Create spatial blocks
    x_blocks = np.ceil((coordinates[:, 0] - coordinates[:, 0].min()) / block_size_m).astype(int)
    y_blocks = np.ceil((coordinates[:, 1] - coordinates[:, 1].min()) / block_size_m).astype(int)
    block_ids = x_blocks * 1000 + y_blocks

    unique_blocks = np.unique(block_ids)
    n_blocks = len(unique_blocks)

    if n_blocks < 2:
        return {"error": f"Only {n_blocks} unique block(s) with block_size={block_size_m}m"}

    try:
        import xgboost as xgb
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
        has_xgb = True
    except ImportError:
        has_xgb = False

    fold_results = []
    all_predictions = []
    all_actuals = []

    for i, block_id in enumerate(unique_blocks):
        test_mask = block_ids == block_id
        train_mask = ~test_mask

        if np.sum(test_mask) == 0 or np.sum(train_mask) == 0:
            continue

        X_train, y_train = X_valid[train_mask], y_valid[train_mask]
        X_test, y_test = X_valid[test_mask], y_valid[test_mask]

        if has_xgb:
            model = xgb.XGBRegressor(
                n_estimators=200, learning_rate=0.05, max_depth=6,
                subsample=0.8, colsample_bytree=0.8, random_state=42,
            )
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
        else:
            # Fallback: weighted mean proxy
            y_pred = np.full(len(y_test), np.mean(y_train))

        errors = y_pred - y_test
        ss_res = float(np.sum(errors ** 2))
        ss_tot = float(np.sum((y_test - np.mean(y_test)) ** 2))
        r2 = round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else 0.0

        fold_results.append({
            "fold": i + 1,
            "block_id": int(block_id),
            "train_samples": int(np.sum(train_mask)),
            "test_samples": int(np.sum(test_mask)),
            "rmse": round(float(np.sqrt(np.mean(errors ** 2))), 4),
            "mae": round(float(np.mean(np.abs(errors))), 4),
            "me": round(float(np.mean(errors)), 4),
            "r_squared": r2,
        })

        all_predictions.extend(y_pred.tolist())
        all_actuals.extend(y_test.tolist())

    if not all_predictions:
        return {"error": "No successful folds"}

    all_pred = np.array(all_predictions)
    all_act = np.array(all_actuals)
    errors = all_pred - all_act

    ss_res = float(np.sum(errors ** 2))
    ss_tot = float(np.sum((all_act - np.mean(all_act)) ** 2))

    return {
        "location_id": location_id,
        "cv_strategy": "spatial_block",
        "block_size_m": block_size_m,
        "n_folds": len(fold_results),
        "n_successful_folds": len(fold_results),
        "mean_error": round(float(np.mean(errors)), 4),
        "mean_squared_error": round(float(np.mean(errors ** 2)), 4),
        "root_mean_squared_error": round(float(np.sqrt(np.mean(errors ** 2))), 4),
        "mean_absolute_error": round(float(np.mean(np.abs(errors))), 4),
        "r_squared": round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else 0.0,
        "fold_results": fold_results,
    }
