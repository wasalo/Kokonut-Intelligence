"""Tenant-scoped read-only aggregates for verified farm energy readings."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_RENEWABLE_SOURCE_TYPES = frozenset({"solar", "wind", "biogas", "biomass"})
_LEGACY_EMISSION_FACTORS_KG_CO2E_PER_KWH = {
    "grid": 0.45,
    "diesel_generator": 0.70,
    "solar": 0.0,
    "wind": 0.0,
    "biogas": 0.05,
    "biomass": 0.10,
    "battery": 0.0,
}


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _iso(value):
    return value.isoformat() if value is not None else None


def get_location_energy_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded kWh aggregates for verified/approved readings only.

    Costs, notes, source names, device identifiers, and arbitrary metadata are
    deliberately excluded. The grouping dimensions are constrained by the
    source schema's CHECK values, so result size is bounded independently of
    farm history volume.
    """
    try:
        operator_id = str(UUID(str(operator_id)))
        location_id = str(UUID(str(location_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="energy_monitoring",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT er.reading_type,
                       es.source_type,
                       COALESCE(er.activity_type, 'unspecified') AS activity_type,
                       COUNT(*)::bigint AS reading_count,
                       SUM(er.kwh)::numeric AS total_kwh,
                       MIN(er.reading_date) AS first_reading_date,
                       MAX(er.reading_date) AS last_reading_date
                  FROM energy_reading AS er
                  JOIN energy_source AS es
                    ON es.id = er.source_id
                   AND es.location_id = er.location_id
                 WHERE er.location_id = %s::uuid
                   AND er.status IN ('verified', 'approved')
                 GROUP BY er.reading_type, es.source_type,
                          COALESCE(er.activity_type, 'unspecified')
                 ORDER BY er.reading_type, es.source_type,
                          COALESCE(er.activity_type, 'unspecified')
                """,
                (location_id,),
            )
            columns = [column[0] for column in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT es.source_type,
                       SUM(CASE WHEN er.reading_type = 'consumption' THEN er.kwh ELSE 0 END)::numeric AS consumption_kwh,
                       SUM(CASE WHEN er.reading_type = 'production' THEN er.kwh ELSE 0 END)::numeric AS production_kwh
                  FROM energy_reading AS er
                  JOIN energy_source AS es
                    ON es.id = er.source_id
                   AND es.location_id = er.location_id
                 WHERE er.location_id = %s::uuid
                   AND er.reading_date >= CURRENT_DATE - INTERVAL '30 days'
                   AND er.status IN ('verified', 'approved')
                 GROUP BY es.source_type
                 ORDER BY es.source_type
                """,
                (location_id,),
            )
            calculation_columns = [column[0] for column in cur.description]
            calculation_rows = [
                dict(zip(calculation_columns, row)) for row in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT er.reading_date,
                       SUM(CASE WHEN er.reading_type = 'consumption' THEN er.kwh ELSE 0 END)::numeric AS consumption_kwh,
                       SUM(CASE WHEN er.reading_type = 'production' THEN er.kwh ELSE 0 END)::numeric AS production_kwh
                  FROM energy_reading AS er
                  JOIN energy_source AS es
                    ON es.id = er.source_id
                   AND es.location_id = er.location_id
                 WHERE er.location_id = %s::uuid
                   AND er.reading_date >= CURRENT_DATE - INTERVAL '7 days'
                   AND er.status IN ('verified', 'approved')
                 GROUP BY er.reading_date
                 ORDER BY er.reading_date
                """,
                (location_id,),
            )
            trend_columns = [column[0] for column in cur.description]
            trend_rows = [dict(zip(trend_columns, row)) for row in cur.fetchall()]

        groups = [
            {
                "reading_type": row["reading_type"],
                "source_type": row["source_type"],
                "activity_type": row["activity_type"],
                "reading_count": int(row["reading_count"] or 0),
                "total_kwh": float(row["total_kwh"] or 0),
                "first_reading_date": _iso(row["first_reading_date"]),
                "last_reading_date": _iso(row["last_reading_date"]),
            }
            for row in rows
        ]
        consumption_kwh = sum(
            float(row["consumption_kwh"] or 0) for row in calculation_rows
        )
        production_kwh = sum(
            float(row["production_kwh"] or 0) for row in calculation_rows
        )
        renewable_consumption_kwh = sum(
            float(row["consumption_kwh"] or 0)
            for row in calculation_rows
            if row["source_type"] in _RENEWABLE_SOURCE_TYPES
        )
        emissions_by_source = []
        for row in calculation_rows:
            source_type = row["source_type"]
            source_consumption_kwh = float(row["consumption_kwh"] or 0)
            emission_factor = _LEGACY_EMISSION_FACTORS_KG_CO2E_PER_KWH.get(
                source_type, 0.0
            )
            emissions_by_source.append(
                {
                    "source_type": source_type,
                    "consumption_kwh": round(source_consumption_kwh, 2),
                    "emission_factor_kg_co2e_per_kwh": emission_factor,
                    "estimated_emissions_kg_co2e": round(
                        source_consumption_kwh * emission_factor, 2
                    ),
                }
            )
        estimated_emissions_kg = sum(
            float(row["consumption_kwh"] or 0)
            * _LEGACY_EMISSION_FACTORS_KG_CO2E_PER_KWH.get(row["source_type"], 0.0)
            for row in calculation_rows
        )
        renewable_share_pct = (
            round(renewable_consumption_kwh / consumption_kwh * 100, 2)
            if consumption_kwh > 0
            else 0
        )
        energy_calculations = {
            "period_days": 30,
            "total_consumption_kwh": round(consumption_kwh, 2),
            "total_production_kwh": round(production_kwh, 2),
            "net_energy_kwh": round(production_kwh - consumption_kwh, 2),
            "renewable_consumption_kwh": round(renewable_consumption_kwh, 2),
            "renewable_share_pct": renewable_share_pct,
            "legacy_carbon_estimate": {
                "model": "legacy_source_type_factors_v1",
                "total_emissions_kg_co2e": round(estimated_emissions_kg, 2),
                "intensity_kg_co2e_per_kwh": (
                    round(estimated_emissions_kg / consumption_kwh, 4)
                    if consumption_kwh > 0
                    else 0
                ),
                "by_source_type": emissions_by_source,
            },
            "trend_7d": [
                {
                    "reading_date": _iso(row["reading_date"]),
                    "consumption_kwh": round(float(row["consumption_kwh"] or 0), 2),
                    "production_kwh": round(float(row["production_kwh"] or 0), 2),
                }
                for row in trend_rows
            ],
        }
        return {
            "location_id": location_id,
            "unit": "kWh",
            "verified_reading_count": sum(row["reading_count"] for row in groups),
            "groups": groups,
            "dashboard_calculations": energy_calculations,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
