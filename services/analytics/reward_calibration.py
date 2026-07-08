"""Reward calibration analytics: maps real-world outputs to token emission rates."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_reward_calibration(conn, location_id: str) -> dict[str, Any]:
    """Compute reward calibration metrics from token reward distributions."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT reward_type, token_type,
               COUNT(*) AS distribution_count,
               SUM(token_amount) AS total_tokens,
               SUM(usd_value) AS total_usd,
               AVG(token_amount) AS avg_per_distribution,
               linked_metric_key,
               AVG(linked_metric_value) AS avg_metric_value,
               distribution_method,
               COUNT(CASE WHEN is_onchain THEN 1 END) AS onchain_count,
               COUNT(CASE WHEN NOT is_onchain THEN 1 END) AS offchain_count
        FROM token_reward_distribution
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY reward_type, token_type, linked_metric_key, distribution_method
        ORDER BY total_tokens DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    distributions = []
    for row in rows:
        distributions.append({
            "reward_type": row[0],
            "token_type": row[1],
            "distribution_count": row[2],
            "total_tokens": round(float(row[3] or 0), 8),
            "total_usd": round(float(row[4] or 0), 2),
            "avg_per_distribution": round(float(row[5] or 0), 8),
            "linked_metric_key": row[6],
            "avg_metric_value": round(float(row[7] or 0), 4),
            "distribution_method": row[8],
            "onchain_count": row[9],
            "offchain_count": row[10],
        })
    total_tokens = sum(d["total_tokens"] for d in distributions)
    total_usd = sum(d["total_usd"] for d in distributions)
    total_onchain = sum(d["onchain_count"] for d in distributions)
    total_offchain = sum(d["offchain_count"] for d in distributions)
    return {
        "location_id": location_id,
        "distributions": distributions,
        "total_distributions": len(distributions),
        "total_tokens": round(total_tokens, 8),
        "total_usd": round(total_usd, 2),
        "onchain_count": total_onchain,
        "offchain_count": total_offchain,
    }


def compute_reward_metric_correlation(conn, location_id: str) -> dict[str, Any]:
    """Compute correlation between linked metrics and token rewards."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT linked_metric_key,
               AVG(linked_metric_value) AS avg_metric,
               AVG(token_amount) AS avg_tokens,
               COUNT(*) AS sample_count,
               CORR(linked_metric_value, token_amount) AS correlation
        FROM token_reward_distribution
        WHERE location_id = %s
          AND status IN ('verified', 'published')
          AND linked_metric_value IS NOT NULL
          AND linked_metric_key IS NOT NULL
        GROUP BY linked_metric_key
        HAVING COUNT(*) >= 2
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    correlations = []
    for row in rows:
        correlations.append({
            "metric_key": row[0],
            "avg_metric_value": round(float(row[1] or 0), 4),
            "avg_tokens": round(float(row[2] or 0), 8),
            "sample_count": row[3],
            "correlation": round(float(row[4] or 0), 4) if row[4] is not None else None,
        })
    return {
        "location_id": location_id,
        "correlations": correlations,
        "metrics_with_correlation": len(correlations),
    }


def compute_reward_calibration_model(conn, location_id: str) -> dict[str, Any]:
    """Summarize reward calibration model runs."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT model_name, model_type, run_date,
               input_metrics, output_weights,
               calibration_score, total_tokens_distributed,
               token_per_unit_output, epoch, confidence_level
        FROM reward_calibration_model
        WHERE location_id = %s AND status IN ('verified', 'published')
        ORDER BY run_date DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    models = []
    for row in rows:
        models.append({
            "model_name": row[0],
            "model_type": row[1],
            "run_date": str(row[2]) if row[2] else None,
            "input_metrics": row[3],
            "output_weights": row[4],
            "calibration_score": round(float(row[5] or 0), 4),
            "total_tokens_distributed": round(float(row[6] or 0), 8),
            "token_per_unit_output": round(float(row[7] or 0), 8),
            "epoch": row[8],
            "confidence_level": round(float(row[9] or 0), 2),
        })
    return {
        "location_id": location_id,
        "models": models,
        "total_model_runs": len(models),
        "latest_calibration_score": models[0]["calibration_score"] if models else None,
    }
