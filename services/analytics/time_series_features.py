"""Time-series aggregation: seasonal medians and multi-year summaries for remote sensing and weather."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger(__name__)


def get_season(target_date: date) -> str:
    """Determine season from date (Northern Hemisphere)."""
    month = target_date.month
    if month in (3, 4, 5):
        return "spring"
    elif month in (6, 7, 8):
        return "summer"
    elif month in (9, 10, 11):
        return "autumn"
    else:
        return "winter"


def compute_window(target_date: date, window_months: int = 6) -> tuple[date, date]:
    """Compute time window ending at target_date."""
    window_end = target_date
    window_start = target_date - timedelta(days=window_months * 30)
    return window_start, window_end


def aggregate_remote_sensing_seasonal(
    conn, location_id: str, target_date: date, window_months: int = 6
) -> list[dict[str, Any]]:
    """Compute seasonal median aggregation of remote sensing observations.

    Implements the ATLAS-SOC simple reducer: arithmetic median over a
    time window ending at the target date.
    """
    window_start, window_end = compute_window(target_date, window_months)

    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ndvi) AS ndvi_median,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ndre) AS ndre_median,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY evi) AS evi_median,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY savi) AS savi_median,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ndwi) AS ndwi_median,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY satvi) AS satvi_median,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY bsi) AS bsi_median,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY nbr2) AS nbr2_median,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ndti) AS ndti_median,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lswi) AS lswi_median,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tc_brightness) AS tc_brightness_median,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tc_greenness) AS tc_greenness_median,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tc_wetness) AS tc_wetness_median,
            MAX(ndvi) - MIN(ndvi) AS ndvi_range,
            STDDEV(ndvi) AS ndvi_stddev,
            COUNT(*) AS observation_count
        FROM remote_sensing_observation
        WHERE location_id = %s
          AND observation_date BETWEEN %s AND %s
        """,
        (location_id, window_start, window_end),
    )
    row = cur.fetchone()
    cur.close()

    if not row or row[12] is None:
        return []

    return [{
        "location_id": location_id,
        "target_date": target_date,
        "reducer_type": "simple_median",
        "window_start": window_start,
        "window_end": window_end,
        "window_months": window_months,
        "ndvi_median": round(float(row[0]), 4) if row[0] else None,
        "ndre_median": round(float(row[1]), 4) if row[1] else None,
        "evi_median": round(float(row[2]), 4) if row[2] else None,
        "savi_median": round(float(row[3]), 4) if row[3] else None,
        "ndwi_median": round(float(row[4]), 4) if row[4] else None,
        "satvi_median": round(float(row[5]), 4) if row[5] else None,
        "bsi_median": round(float(row[6]), 4) if row[6] else None,
        "nbr2_median": round(float(row[7]), 4) if row[7] else None,
        "ndti_median": round(float(row[8]), 4) if row[8] else None,
        "lswi_median": round(float(row[9]), 4) if row[9] else None,
        "tc_brightness_median": round(float(row[10]), 4) if row[10] else None,
        "tc_greenness_median": round(float(row[11]), 4) if row[11] else None,
        "tc_wetness_median": round(float(row[12]), 4) if row[12] else None,
        "ndvi_range": round(float(row[13]), 4) if row[13] else None,
        "ndvi_stddev": round(float(row[14]), 4) if row[14] else None,
        "observation_count": int(row[15]),
    }]


def aggregate_remote_sensing_timeseries(
    conn,
    location_id: str,
    target_date: date,
    months_per_window: int = 3,
    num_windows: int = 8,
) -> list[dict[str, Any]]:
    """Compute time-series summary: sequential 3-month windows over 24 months.

    Implements the ATLAS-SOC time-series summary reducer.
    Generates statistical summaries of land surface conditions over
    the previous 24 months, related to agricultural practices.
    """
    results = []

    for i in range(num_windows):
        window_end = target_date - timedelta(days=i * months_per_window * 30)
        window_start = window_end - timedelta(days=months_per_window * 30)
        year_offset = i // (12 // months_per_window)
        season = get_season(window_end)

        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ndvi) AS ndvi_median,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY savi) AS savi_median,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY satvi) AS satvi_median,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY bsi) AS bsi_median,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY nbr2) AS nbr2_median,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ndti) AS ndti_median,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lswi) AS lswi_median,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tc_brightness) AS tc_brightness_median,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tc_greenness) AS tc_greenness_median,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tc_wetness) AS tc_wetness_median,
                MAX(ndvi) - MIN(ndvi) AS ndvi_range,
                STDDEV(ndvi) AS ndvi_stddev,
                COUNT(*) AS observation_count
            FROM remote_sensing_observation
            WHERE location_id = %s
              AND observation_date BETWEEN %s AND %s
            """,
            (location_id, window_start, window_end),
        )
        row = cur.fetchone()
        cur.close()

        if row and row[12] is not None:
            results.append({
                "location_id": location_id,
                "target_date": target_date,
                "reducer_type": "time_series_summary",
                "window_start": window_start,
                "window_end": window_end,
                "window_months": months_per_window,
                "season": season,
                "year_offset": year_offset,
                "ndvi_median": round(float(row[0]), 4) if row[0] else None,
                "savi_median": round(float(row[1]), 4) if row[1] else None,
                "satvi_median": round(float(row[2]), 4) if row[2] else None,
                "bsi_median": round(float(row[3]), 4) if row[3] else None,
                "nbr2_median": round(float(row[4]), 4) if row[4] else None,
                "ndti_median": round(float(row[5]), 4) if row[5] else None,
                "lswi_median": round(float(row[6]), 4) if row[6] else None,
                "tc_brightness_median": round(float(row[7]), 4) if row[7] else None,
                "tc_greenness_median": round(float(row[8]), 4) if row[8] else None,
                "tc_wetness_median": round(float(row[9]), 4) if row[9] else None,
                "ndvi_range": round(float(row[10]), 4) if row[10] else None,
                "ndvi_stddev": round(float(row[11]), 4) if row[11] else None,
                "observation_count": int(row[12]),
            })

    return results


def aggregate_weather_seasonal(
    conn, location_id: str, target_date: date, window_months: int = 6
) -> Optional[dict[str, Any]]:
    """Compute seasonal mean aggregation of weather observations."""
    window_start, window_end = compute_window(target_date, window_months)

    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            AVG(temperature_c) AS mean_temp,
            MAX(temp_max_c) AS max_temp,
            MIN(temp_min_c) AS min_temp,
            SUM(precipitation_mm) AS total_precip,
            AVG(solar_radiation_wm2) AS mean_solar,
            COUNT(*) AS observation_count
        FROM weather_observation
        WHERE location_id = %s
          AND observation_date BETWEEN %s AND %s
        """,
        (location_id, window_start, window_end),
    )
    row = cur.fetchone()
    cur.close()

    if not row or row[5] is None:
        return None

    mean_temp = float(row[0]) if row[0] else 0
    max_temp = float(row[1]) if row[1] else 0
    min_temp = float(row[2]) if row[2] else 0

    return {
        "location_id": location_id,
        "target_date": target_date,
        "reducer_type": "seasonal_mean",
        "window_start": window_start,
        "window_end": window_end,
        "season": get_season(target_date),
        "mean_temp_mean": round(mean_temp, 2),
        "max_temp_mean": round(max_temp, 2),
        "min_temp_mean": round(min_temp, 2),
        "temp_range": round(max_temp - min_temp, 2),
        "precipitation_sum": round(float(row[3]) if row[3] else 0, 2),
        "observation_count": int(row[5]),
    }


def build_complete_feature_set(
    conn, location_id: str, target_date: date
) -> dict[str, Any]:
    """Build the complete feature set for SOC prediction at a location and date.

    Combines:
    - Simple reducer (6-month median) from remote sensing
    - Time-series summary (3-month windows over 24 months)
    - Weather seasonal means
    - WorldClim long-term climate proxies
    """
    # Simple reducer
    simple = aggregate_remote_sensing_seasonal(conn, location_id, target_date)

    # Time-series summary
    timeseries = aggregate_remote_sensing_timeseries(conn, location_id, target_date)

    # Weather
    weather = aggregate_weather_seasonal(conn, location_id, target_date)

    # WorldClim
    cur = conn.cursor()
    cur.execute(
        """
        SELECT bio1_mean_annual_temp, bio16_precip_wettest_quarter,
               bio17_precip_driest_quarter
        FROM worldclim_climate
        WHERE location_id = %s
        LIMIT 1
        """,
        (location_id,),
    )
    wc = cur.fetchone()
    cur.close()

    features = {}

    # Simple reducer features
    if simple:
        s = simple[0]
        for key in [
            "ndvi_median", "savi_median", "satvi_median", "bsi_median",
            "nbr2_median", "ndti_median", "lswi_median",
            "tc_brightness_median", "tc_greenness_median", "tc_wetness_median",
            "ndvi_range", "ndvi_stddev",
        ]:
            features[key] = s.get(key)

    # Time-series features (use most recent window for each season)
    for ts in timeseries:
        season = ts.get("season", "unknown")
        year = ts.get("year_offset", 0)
        prefix = f"ts_{season}_y{year}"
        for key in ["ndvi_median", "savi_median", "bsi_median", "lswi_median", "tc_greenness_median"]:
            features[f"{prefix}_{key}"] = ts.get(key)

    # Weather
    if weather:
        features["weather_mean_temp"] = weather.get("mean_temp_mean")
        features["weather_total_precip"] = weather.get("precipitation_sum")
        features["weather_temp_range"] = weather.get("temp_range")

    # WorldClim
    if wc:
        features["worldclim_bio1"] = round(float(wc[0]), 2) if wc[0] else None
        features["worldclim_bio16"] = round(float(wc[1]), 2) if wc[1] else None
        features["worldclim_bio17"] = round(float(wc[2]), 2) if wc[2] else None

    # Location
    features["location_id"] = location_id
    features["target_date"] = target_date

    return features
