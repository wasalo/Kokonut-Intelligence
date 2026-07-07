"""Model validation analytics: prediction accuracy, feature importance, backtesting."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_prediction_accuracy(conn, location_id: str) -> dict[str, Any]:
    """Compute prediction accuracy metrics across model types."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT model_type, metric_name, unit,
               COUNT(*) AS prediction_count,
               AVG(absolute_error) AS avg_absolute_error,
               AVG(percentage_error) AS avg_percentage_error,
               AVG(mae) AS avg_mae,
               AVG(rmse) AS avg_rmse,
               AVG(mape) AS avg_mape,
               AVG(r_squared) AS avg_r_squared,
               MIN(prediction_date) AS first_prediction,
               MAX(actual_date) AS last_actual
        FROM prediction_accuracy_record
        WHERE location_id = %s AND status IN ('verified', 'published')
          AND actual_value IS NOT NULL
        GROUP BY model_type, metric_name, unit
        ORDER BY avg_mape ASC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    models = []
    for row in rows:
        models.append({
            "model_type": row[0],
            "metric_name": row[1],
            "unit": row[2],
            "prediction_count": row[3],
            "avg_absolute_error": round(float(row[4] or 0), 4),
            "avg_percentage_error": round(float(row[5] or 0), 2),
            "avg_mae": round(float(row[6] or 0), 4),
            "avg_rmse": round(float(row[7] or 0), 4),
            "avg_mape": round(float(row[8] or 0), 2),
            "avg_r_squared": round(float(row[9] or 0), 4),
            "first_prediction": str(row[10]) if row[10] else None,
            "last_actual": str(row[11]) if row[11] else None,
        })
    overall_mape = (
        sum(m["avg_mape"] * m["prediction_count"] for m in models)
        / max(sum(m["prediction_count"] for m in models), 1)
    )
    overall_accuracy = 100 - overall_mape
    return {
        "location_id": location_id,
        "models": models,
        "total_model_types": len(models),
        "overall_mape_pct": round(overall_mape, 2),
        "overall_accuracy_pct": round(overall_accuracy, 2),
        "best_performing_model": models[0]["model_type"] if models else None,
    }


def compute_feature_importance(conn, location_id: str) -> dict[str, Any]:
    """Compute feature importance analysis across model types."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT model_type, feature_name,
               AVG(importance_score) AS avg_importance,
               AVG(correlation_coefficient) AS avg_correlation,
               AVG(p_value) AS avg_p_value,
               COUNT(*) AS analysis_count,
               MODE() WITHIN GROUP (ORDER BY direction) AS most_common_direction
        FROM feature_importance_record
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY model_type, feature_name
        ORDER BY avg_importance DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    features = []
    for row in rows:
        features.append({
            "model_type": row[0],
            "feature_name": row[1],
            "avg_importance_score": round(float(row[2] or 0), 4),
            "avg_correlation": round(float(row[3] or 0), 4),
            "avg_p_value": round(float(row[4] or 0), 6),
            "analysis_count": row[5],
            "direction": row[6],
        })
    by_model = {}
    for f in features:
        mt = f["model_type"]
        if mt not in by_model:
            by_model[mt] = []
        by_model[mt].append(f)
    top_predictors = {}
    for mt, feats in by_model.items():
        if feats:
            top_predictors[mt] = feats[0]["feature_name"]
    return {
        "location_id": location_id,
        "features": features,
        "total_features_analyzed": len(features),
        "top_predictors_by_model": top_predictors,
        "models_analyzed": list(by_model.keys()),
    }


def compute_backtest_summary(conn, location_id: str) -> dict[str, Any]:
    """Summarize backtest results by comparing predicted vs actual across all records."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT model_type,
               COUNT(*) AS total_predictions,
               SUM(CASE WHEN ABS(percentage_error) <= 10 THEN 1 ELSE 0 END) AS within_10pct,
               SUM(CASE WHEN ABS(percentage_error) <= 20 THEN 1 ELSE 0 END) AS within_20pct,
               SUM(CASE WHEN actual_value > predicted_value THEN 1 ELSE 0 END) AS underpredicted,
               SUM(CASE WHEN actual_value < predicted_value THEN 1 ELSE 0 END) AS overpredicted,
               AVG(absolute_error) AS mean_absolute_error,
               SQRT(AVG(squared_error)) AS root_mean_squared_error,
               AVG(percentage_error) AS mean_percentage_error
        FROM prediction_accuracy_record
        WHERE location_id = %s AND status IN ('verified', 'published')
          AND actual_value IS NOT NULL
        GROUP BY model_type
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    backtests = []
    for row in rows:
        total = row[1]
        backtests.append({
            "model_type": row[0],
            "total_predictions": total,
            "within_10pct_count": row[2],
            "within_20pct_count": row[3],
            "underpredicted_count": row[4],
            "overpredicted_count": row[5],
            "within_10pct_pct": round((row[2] or 0) / max(total, 1) * 100, 2),
            "within_20pct_pct": round((row[3] or 0) / max(total, 1) * 100, 2),
            "mean_absolute_error": round(float(row[6] or 0), 4),
            "rmse": round(float(row[7] or 0), 4),
            "mean_percentage_error": round(float(row[8] or 0), 2),
        })
    return {
        "location_id": location_id,
        "backtests": backtests,
        "total_model_types": len(backtests),
    }
