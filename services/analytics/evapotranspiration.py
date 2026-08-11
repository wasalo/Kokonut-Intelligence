#!/usr/bin/env python3
"""
Evapotranspiration — FAO-56 Penman-Monteith ET₀ and Crop ETc

Computes reference evapotranspiration (ET₀) using the FAO-56
Penman-Monteith equation, crop-specific ETc, and field-level water balance.

Usage:
    python -m services.analytics.evapotranspiration --location-id <uuid> --compute
    python -m services.analytics.evapotranspiration --location-id <uuid> --water-balance
    python -m services.analytics.evapotranspiration --et0 --temp-max 32 --temp-min 18 \
        --humidity 65 --wind 12 --solar 18 --elevation 1500 --lat -1.2 --doy 180
"""

import json
import math
from datetime import datetime, timezone, date, timedelta
from typing import Optional

from ..common.commands import CommandLine
from ..common.logging import get_logger

logger = get_logger("analytics.evapotranspiration")

# Stefan-Boltzmann constant (MJ K⁻⁴ m⁻² d⁻¹)
STEFAN_BOLTZMANN = 4.903e-9

# Latent heat of vaporization (MJ/kg)
LAMBDA_V = 2.45

# Atmosphere pressure at elevation (kPa) — approximate
P_ATM_SEA_LEVEL = 101.3


# ============================================================
# FAO-56 Penman-Monteith ET₀
# ============================================================

def compute_atmospheric_pressure(elevation_m: float) -> float:
    """Atmospheric pressure at elevation (kPa)."""
    return P_ATM_SEA_LEVEL * ((293 - 0.0065 * elevation_m) / 293) ** 5.26


def compute_psychnometric_constant(atm_pressure: float, elevation_m: float) -> float:
    """Psychrometric constant (kPa/°C)."""
    return 0.000665 * atm_pressure


def compute_saturation_vapor_pressure(temp_c: float) -> float:
    """Saturation vapor pressure at temperature (kPa)."""
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))


def compute_vapor_pressure_deficit(temp_max: float, temp_min: float,
                                     humidity: float) -> float:
    """Vapor pressure deficit (kPa).
    
    Args:
        temp_max: Daily maximum temperature (°C)
        temp_min: Daily minimum temperature (°C)
        humidity: Mean relative humidity (%)
    """
    es_max = compute_saturation_vapor_pressure(temp_max)
    es_min = compute_saturation_vapor_pressure(temp_min)
    es_mean = (es_max + es_min) / 2
    ea = (humidity / 100) * es_mean
    return max(es_mean - ea, 0)


def compute_net_radiation(temp_max: float, temp_min: float,
                           solar_radiation: float, elevation_m: float,
                           latitude: float, day_of_year: int,
                           albedo: float = 0.23) -> float:
    """Net radiation at crop surface (MJ m⁻² d⁻¹).
    
    Args:
        temp_max: Daily max temperature (°C)
        temp_min: Daily min temperature (°C)
        solar_radiation: Incoming solar radiation (MJ m⁻² d⁻¹)
        elevation_m: Station elevation (m)
        latitude: Station latitude (decimal degrees)
        day_of_year: Day of year (1-365)
        albedo: Crop albedo (0.23 for reference grass)
    """
    # Inverse relative distance Earth-Sun
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    # Solar declination
    delta = 0.408 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    # Latitude in radians
    phi = math.radians(latitude)
    # Sunset hour angle
    lat_sin = math.sin(phi)
    lat_cos = math.cos(phi)
    ws = math.acos(-math.tan(phi) * math.tan(delta))
    # Extraterrestrial radiation (MJ m⁻² d⁻¹)
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        lat_sin * math.sin(delta) * ws +
        lat_cos * math.cos(delta) * math.sin(ws)
    )
    # Clear-sky radiation
    rso = (0.75 + 2e-5 * elevation_m) * ra
    # Net shortwave radiation
    rns = (1 - albedo) * solar_radiation
    # Net longwave radiation
    t_max_k = temp_max + 273.16
    t_min_k = temp_min + 273.16
    rnl = STEFAN_BOLTZMANN * (
        (t_max_k**4 + t_min_k**4) / 2
    ) * (0.34 - 0.14 * math.sqrt(max(ea_vapor_pressure(temp_max, temp_min), 0.01))) * (
        1.35 * min(solar_radiation / max(rso, 0.01), 1.0) - 0.35
    )
    return rns - rnl


def ea_vapor_pressure(temp_max: float, temp_min: float) -> float:
    """Actual vapor pressure from temp max/min (kPa)."""
    es_max = compute_saturation_vapor_pressure(temp_max)
    es_min = compute_saturation_vapor_pressure(temp_min)
    return (es_max + es_min) / 2


def compute_et0_penman_monteith(
    temp_max: float,
    temp_min: float,
    humidity: float,
    wind_speed: float,
    solar_radiation: float,
    elevation_m: float = 0.0,
    latitude: float = 0.0,
    day_of_year: int = 1,
) -> dict:
    """FAO-56 Penman-Monteith reference evapotranspiration (mm/day).
    
    Args:
        temp_max: Daily maximum temperature (°C)
        temp_min: Daily minimum temperature (°C)
        humidity: Mean relative humidity (%)
        wind_speed: Wind speed at 2m height (km/h)
        solar_radiation: Incoming solar radiation (MJ m⁻² d⁻¹). 
            If None or 0, uses Hargreaves fallback.
        elevation_m: Station elevation above sea level (m)
        latitude: Station latitude (decimal degrees, negative = South)
        day_of_year: Day of year (1-365)
    
    Returns:
        dict with et0_mm, method, components
    """
    # Convert wind from km/h to m/s
    wind_ms = wind_speed / 3.6

    # Mean temperature
    temp_mean = (temp_max + temp_min) / 2

    # Atmospheric pressure and psychrometric constant
    p_atm = compute_atmospheric_pressure(elevation_m)
    gamma = compute_psychnometric_constant(p_atm, elevation_m)

    # Saturation vapor pressure
    es = (compute_saturation_vapor_pressure(temp_max) +
          compute_saturation_vapor_pressure(temp_min)) / 2

    # Vapor pressure deficit
    vpd = compute_vapor_pressure_deficit(temp_max, temp_min, humidity)

    # Net radiation (if solar radiation available)
    if solar_radiation and solar_radiation > 0:
        rn = compute_net_radiation(
            temp_max, temp_min, solar_radiation, elevation_m, latitude, day_of_year
        )
        method = "penman_monteith"

        # Soil heat flux (G) — small for daily time step
        g = 0.0

        # Slope of vapor pressure curve
        delta_svp = (4098 * compute_saturation_vapor_pressure(temp_mean)) / (temp_mean + 237.3) ** 2

        # ET₀ (mm/day)
        numerator = (0.408 * delta_svp * (rn - g) +
                     gamma * (900 / (temp_mean + 273)) * wind_ms * vpd)
        denominator = delta_svp + gamma * (1 + 0.34 * wind_ms)
        et0 = max(numerator / denominator, 0)
    else:
        # Hargreaves fallback (temperature-only)
        et0 = _hargreaves_et0(temp_max, temp_min, latitude, day_of_year)
        rn = 0
        method = "hargreaves"

    return {
        "et0_mm": round(et0, 2),
        "method": method,
        "temp_mean": temp_mean,
        "vpd": round(vpd, 3),
        "solar_radiation": solar_radiation or 0,
        "net_radiation": round(rn, 2) if rn else None,
        "wind_speed_ms": round(wind_ms, 2),
        "elevation_m": elevation_m,
    }


def _hargreaves_et0(temp_max: float, temp_min: float,
                     latitude: float, day_of_year: int) -> float:
    """Hargreaves ET₀ estimation (mm/day) — used when solar radiation unavailable."""
    temp_mean = (temp_max + temp_min) / 2
    temp_range = temp_max - temp_min

    # Extraterrestrial radiation (simplified)
    phi = math.radians(latitude)
    delta = 0.408 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    ws = math.acos(-math.tan(phi) * math.tan(delta))
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        math.sin(phi) * math.sin(delta) * ws +
        math.cos(phi) * math.cos(delta) * math.sin(ws)
    )

    # Hargreaves equation
    et0 = 0.0023 * (temp_mean + 17.8) * (temp_range ** 0.5) * ra * 0.408
    return max(et0, 0)


# ============================================================
# Crop ETc
# ============================================================

CROP_KC = {
    "maize": {"initial": 0.3, "development": 0.75, "mid": 1.15, "late": 0.6},
    "cassava": {"initial": 0.4, "development": 0.7, "mid": 1.1, "late": 0.7},
    "beans": {"initial": 0.35, "development": 0.7, "mid": 1.1, "late": 0.65},
    "sweet_potato": {"initial": 0.4, "development": 0.75, "mid": 1.05, "late": 0.6},
    "coffee": {"initial": 0.4, "development": 0.7, "mid": 1.15, "late": 0.7},
    "avocado": {"initial": 0.4, "development": 0.75, "mid": 1.2, "late": 0.8},
    "tomato": {"initial": 0.4, "development": 0.75, "mid": 1.15, "late": 0.8},
    "banana": {"initial": 0.4, "development": 0.7, "mid": 1.2, "late": 0.85},
    "default": {"initial": 0.35, "development": 0.7, "mid": 1.1, "late": 0.65},
}

# Growth stage by GDD fraction of total
STAGE_GDD_FRACTIONS = {
    "initial": (0.0, 0.15),
    "development": (0.15, 0.50),
    "mid": (0.50, 0.85),
    "late": (0.85, 1.0),
}


def get_crop_kc(crop_name: str, growth_stage: str) -> float:
    """Get crop coefficient Kc for a given crop and growth stage."""
    crop_lc = crop_name.lower().strip()
    crop_kc = CROP_KC.get(crop_lc, CROP_KC["default"])
    return crop_kc.get(growth_stage, crop_kc["mid"])


def get_growth_stage_from_gdd(crop_name: str, accumulated_gdd: float,
                               total_gdd: float) -> str:
    """Determine growth stage from GDD accumulation."""
    if total_gdd <= 0:
        return "unknown"
    fraction = accumulated_gdd / total_gdd
    for stage, (low, high) in STAGE_GDD_FRACTIONS.items():
        if low <= fraction < high:
            return stage
    return "late" if fraction >= 1.0 else "initial"


def compute_etc(et0: float, crop_name: str, growth_stage: str) -> dict:
    """Compute crop evapotranspiration ETc.
    
    Args:
        et0: Reference ET (mm/day)
        crop_name: Crop name
        growth_stage: One of initial, development, mid, late
    
    Returns:
        dict with etc_mm, kc, stage
    """
    kc = get_crop_kc(crop_name, growth_stage)
    etc = et0 * kc
    return {
        "etc_mm": round(etc, 2),
        "kc": kc,
        "stage": growth_stage,
        "et0_mm": round(et0, 2),
    }


# ============================================================
# Water Balance
# ============================================================

def compute_water_balance(
    conn,
    location_id: str,
    plot_id: str = None,
    crop_cycle_id: str = None,
    period_days: int = 30,
) -> dict:
    """Compute field-level water balance.
    
    Water input: precipitation + irrigation
    Water output: ETc estimate
    Status: adequate / mild_stress / stressed
    """
    cur = conn.cursor()

    # Get crop info
    crop_name = "default"
    growth_stage = "mid"
    planting_date = None
    total_gdd = 2000

    if crop_cycle_id:
        cur.execute(
            """
            SELECT c.name, cc.planting_date, cg.total_gdd_required
            FROM crop_cycle cc
            JOIN crop c ON c.id = cc.crop_id
            LEFT JOIN crop_gdd_config cg ON cg.crop_name = c.name
            WHERE cc.id = %s
            """,
            (crop_cycle_id,),
        )
        row = cur.fetchone()
        if row:
            crop_name, planting_date, total_gdd = row
            total_gdd = total_gdd or 2000

    # Get recent weather observations
    cur.execute(
        """
        SELECT observation_date,
               COALESCE(precipitation_mm, 0) AS precip,
               COALESCE(temperature_c, (temp_min_c + temp_max_c) / 2) AS temp,
               COALESCE(temp_max_c, temperature_c) AS temp_max,
               COALESCE(temp_min_c, temperature_c) AS temp_min,
               COALESCE(humidity_pct, 70) AS humidity,
               COALESCE(wind_speed_kmh, 5) AS wind,
               COALESCE(solar_radiation_wm2, 0) / 0.0864 AS solar_mj
        FROM weather_observation
        WHERE location_id = %s
          AND observation_date >= CURRENT_DATE - %s
        ORDER BY observation_date
        """,
        (location_id, period_days),
    )
    weather_rows = cur.fetchall()

    if not weather_rows:
        return {
            "location_id": location_id,
            "period_days": period_days,
            "total_rainfall_mm": 0,
            "total_et0_mm": 0,
            "total_etc_mm": 0,
            "water_deficit_mm": 0,
            "water_status": "no_data",
            "daily_data": [],
        }

    total_rainfall = 0
    total_et0 = 0
    total_etc = 0
    daily_data = []

    for row in weather_rows:
        obs_date, precip, temp, temp_max, temp_min, humidity, wind, solar_mj = row

        if temp_max is None or temp_min is None:
            temp_max = temp or 25
            temp_min = temp or 18

        day_of_year = obs_date.timetuple().tm_yday

        et0_result = compute_et0_penman_monteith(
            temp_max=temp_max,
            temp_min=temp_min,
            humidity=humidity or 70,
            wind_speed=wind or 5,
            solar_radiation=solar_mj if solar_mj > 0 else None,
            latitude=0.0,
            day_of_year=day_of_year,
        )
        et0 = et0_result["et0_mm"]
        etc_result = compute_etc(et0, crop_name, growth_stage)
        etc = etc_result["etc_mm"]

        total_rainfall += precip or 0
        total_et0 += et0
        total_etc += etc

        daily_data.append({
            "date": obs_date.isoformat(),
            "precipitation_mm": round(precip or 0, 2),
            "et0_mm": round(et0, 2),
            "etc_mm": round(etc, 2),
        })

    water_deficit = total_etc - total_rainfall
    if total_etc == 0:
        water_status = "no_data"
    elif total_rainfall < total_etc * 0.5:
        water_status = "stressed"
    elif total_rainfall < total_etc * 0.8:
        water_status = "mild_stress"
    else:
        water_status = "adequate"

    cur.close()

    return {
        "location_id": location_id,
        "crop_cycle_id": crop_cycle_id,
        "crop_name": crop_name,
        "growth_stage": growth_stage,
        "period_days": period_days,
        "total_rainfall_mm": round(total_rainfall, 2),
        "total_et0_mm": round(total_et0, 2),
        "total_etc_mm": round(total_etc, 2),
        "water_deficit_mm": round(water_deficit, 2),
        "water_status": water_status,
        "daily_data": daily_data,
    }


# ============================================================
# Storage
# ============================================================

def store_et_forecast(conn, location_id: str) -> int:
    """Compute ET₀ for weather forecasts and store in weather_forecast.et0_estimate_mm."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, forecast_date, forecast_hour,
               temp_c, temp_min_c, temp_max_c, humidity_pct,
               wind_speed_kmh, solar_radiation_wm2
        FROM weather_forecast
        WHERE location_id = %s
          AND et0_estimate_mm IS NULL
          AND temp_c IS NOT NULL
        ORDER BY forecast_date, forecast_hour
        """,
        (location_id,),
    )
    rows = cur.fetchall()

    updated = 0
    for row in rows:
        wf_id, fdate, fhour, temp, tmin, tmax, humidity, wind, solar = row

        if tmax is None or tmin is None:
            tmax = temp or 25
            tmin = temp or 18

        day_of_year = fdate.timetuple().tm_yday
        solar_mj = (solar or 0) / 0.0864 if solar else None

        et0_result = compute_et0_penman_monteith(
            temp_max=tmax,
            temp_min=tmin,
            humidity=humidity or 70,
            wind_speed=wind or 5,
            solar_radiation=solar_mj,
            latitude=0.0,
            day_of_year=day_of_year,
        )

        cur.execute(
            "UPDATE weather_forecast SET et0_estimate_mm = %s WHERE id = %s",
            (et0_result["et0_mm"], wf_id),
        )
        updated += 1

    conn.commit()
    cur.close()
    return updated


# ============================================================
# CLI
# ============================================================

cli = CommandLine(
    "evapotranspiration",
    "Evapotranspiration computation (FAO-56 Penman-Monteith)",
)


def _cmd_et0(db, a):
    doy = a.doy or datetime.now().timetuple().tm_yday
    return compute_et0_penman_monteith(
        temp_max=a.temp_max,
        temp_min=a.temp_min,
        humidity=a.humidity,
        wind_speed=a.wind,
        solar_radiation=a.solar,
        elevation_m=a.elevation,
        latitude=a.lat,
        day_of_year=doy,
    )


def _render_et0(result, a):
    if a.json:
        print(json.dumps(result, indent=2))
        return
    print(f"ET₀: {result['et0_mm']} mm/day ({result['method']})")
    print(f"  VPD: {result['vpd']:.3f} kPa")
    print(f"  Wind: {result['wind_speed_ms']:.1f} m/s")


def _cmd_water_balance(db, a):
    return compute_water_balance(
        db, a.location_id, a.plot_id, a.crop_cycle_id, a.period
    )


def _render_water_balance(result, a):
    if a.json:
        print(json.dumps(result, indent=2, default=str))
        return
    print(f"Water Balance — {result['crop_name']} ({result['growth_stage']})")
    print(f"  Rainfall: {result['total_rainfall_mm']} mm")
    print(f"  ET₀: {result['total_et0_mm']} mm")
    print(f"  ETc: {result['total_etc_mm']} mm")
    print(f"  Deficit: {result['water_deficit_mm']} mm")
    print(f"  Status: {result['water_status']}")


def _cmd_store_et(db, a):
    return store_et_forecast(db, a.location_id)


def _render_store_et(result, a):
    print(f"Updated {result} forecast records with ET₀ estimates")


cli.subcommand("et0", "Compute ET₀ from weather parameters") \
    .add("--temp-max", type=float, required=True, help="Max temp (°C)") \
    .add("--temp-min", type=float, required=True, help="Min temp (°C)") \
    .add("--humidity", type=float, default=65, help="Relative humidity (%)") \
    .add("--wind", type=float, default=5, help="Wind speed (km/h)") \
    .add("--solar", type=float, default=None, help="Solar radiation (MJ/m²/d)") \
    .add("--elevation", type=float, default=0, help="Elevation (m)") \
    .add("--lat", type=float, default=0, help="Latitude (decimal degrees)") \
    .add("--doy", type=int, default=None, help="Day of year") \
    .add("--json", action="store_true", help="JSON output") \
    .run(_cmd_et0, needs_db=False) \
    .render_with(_render_et0)

cli.subcommand("water-balance", "Compute water balance for a location") \
    .add("--location-id", required=True, help="Location UUID") \
    .add("--plot-id", help="Plot UUID (optional)") \
    .add("--crop-cycle-id", help="Crop cycle UUID (optional)") \
    .add("--period", type=int, default=30, help="Period in days") \
    .add("--json", action="store_true", help="JSON output") \
    .run(_cmd_water_balance) \
    .render_with(_render_water_balance)

cli.subcommand("store-et", "Compute and store ET₀ for weather forecasts") \
    .add("--location-id", required=True, help="Location UUID") \
    .run(_cmd_store_et) \
    .render_with(_render_store_et)


def main(argv=None):
    return cli.run(argv)


if __name__ == "__main__":
    main()
