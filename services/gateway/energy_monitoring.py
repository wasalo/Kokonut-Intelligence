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
    """Return bounded, location-scoped energy aggregates for reviewed readings.

    Costs are grouped only by recorded currency. Notes, source names, device
    identifiers, and arbitrary metadata are deliberately excluded. The
    grouping dimensions are constrained by schema enums, so response size is
    bounded independently of farm history volume.
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

            cur.execute(
                """
                SELECT res.renewable_type,
                       COUNT(*)::bigint AS source_count,
                       SUM(res.rated_capacity_kw)::numeric AS capacity_kw,
                       SUM(res.annual_generation_kwh)::numeric AS annual_generation_kwh,
                       SUM(res.carbon_offset_kg)::numeric AS registered_carbon_offset_kg
                  FROM renewable_energy_source AS res
                  JOIN energy_source AS es
                    ON es.id = res.source_id
                   AND es.location_id = res.location_id
                 WHERE res.location_id = %s::uuid
                   AND res.status = 'active'
                 GROUP BY res.renewable_type
                 ORDER BY res.renewable_type
                """,
                (location_id,),
            )
            renewable_columns = [column[0] for column in cur.description]
            renewable_rows = [dict(zip(renewable_columns, row)) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT COALESCE(SUM(er.kwh), 0)::numeric AS annual_consumption_kwh
                  FROM energy_reading AS er
                  JOIN energy_source AS es
                    ON es.id = er.source_id
                   AND es.location_id = er.location_id
                 WHERE er.location_id = %s::uuid
                   AND er.reading_type = 'consumption'
                   AND er.reading_date >= CURRENT_DATE - INTERVAL '365 days'
                   AND er.status IN ('verified', 'approved')
                """,
                (location_id,),
            )
            annual_consumption_row = cur.fetchone()

            cur.execute(
                """
                SELECT er.cost_currency_code,
                       SUM(COALESCE(er.total_cost, er.kwh * er.cost_per_kwh))::numeric AS total_cost,
                       SUM(er.kwh)::numeric AS costed_kwh,
                       COUNT(*)::bigint AS reading_count
                  FROM energy_reading AS er
                  JOIN energy_source AS es
                    ON es.id = er.source_id
                   AND es.location_id = er.location_id
                 WHERE er.location_id = %s::uuid
                   AND er.reading_type = 'consumption'
                   AND er.reading_date >= CURRENT_DATE - INTERVAL '30 days'
                   AND er.status IN ('verified', 'approved')
                   AND er.cost_currency_code IS NOT NULL
                   AND COALESCE(er.total_cost, er.kwh * er.cost_per_kwh) IS NOT NULL
                 GROUP BY er.cost_currency_code
                 ORDER BY er.cost_currency_code
                """,
                (location_id,),
            )
            energy_cost_columns = [column[0] for column in cur.description]
            energy_cost_rows = [dict(zip(energy_cost_columns, row)) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT COUNT(*)::bigint AS unclassified_cost_reading_count
                  FROM energy_reading AS er
                  JOIN energy_source AS es
                    ON es.id = er.source_id
                   AND es.location_id = er.location_id
                 WHERE er.location_id = %s::uuid
                   AND er.reading_type = 'consumption'
                   AND er.reading_date >= CURRENT_DATE - INTERVAL '30 days'
                   AND er.status IN ('verified', 'approved')
                   AND COALESCE(er.total_cost, er.kwh * er.cost_per_kwh) IS NOT NULL
                   AND er.cost_currency_code IS NULL
                """,
                (location_id,),
            )
            unclassified_cost_row = cur.fetchone()

            cur.execute(
                """
                SELECT eel.log_date,
                       eel.period,
                       eel.total_consumption_kwh,
                       eel.total_production_kwh,
                       eel.net_energy_kwh,
                       eel.renewable_pct,
                       eel.carbon_intensity_kg_kwh
                  FROM energy_efficiency_log AS eel
                 WHERE eel.location_id = %s::uuid
                   AND eel.period = 'daily'
                   AND eel.status IN ('verified', 'approved')
                 ORDER BY eel.log_date DESC
                 LIMIT 12
                """,
                (location_id,),
            )
            efficiency_columns = [column[0] for column in cur.description]
            efficiency_rows = [
                dict(zip(efficiency_columns, row)) for row in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT es.source_type,
                       COUNT(*)::bigint AS source_count,
                       SUM(es.capacity_kw)::numeric AS capacity_kw
                  FROM energy_source AS es
                 WHERE es.location_id = %s::uuid
                   AND es.status = 'active'
                 GROUP BY es.source_type
                 ORDER BY es.source_type
                """,
                (location_id,),
            )
            source_columns = [column[0] for column in cur.description]
            active_source_rows = [
                dict(zip(source_columns, row)) for row in cur.fetchall()
            ]

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
        renewable_by_type = [
            {
                "renewable_type": row["renewable_type"],
                "source_count": int(row["source_count"] or 0),
                "capacity_kw": round(float(row["capacity_kw"] or 0), 2),
                "annual_generation_kwh": round(
                    float(row["annual_generation_kwh"] or 0), 2
                ),
                "registered_carbon_offset_kg": round(
                    float(row["registered_carbon_offset_kg"] or 0), 2
                ),
            }
            for row in renewable_rows
        ]
        registered_capacity_kw = sum(row["capacity_kw"] for row in renewable_by_type)
        registered_generation_kwh = sum(
            row["annual_generation_kwh"] for row in renewable_by_type
        )
        registered_carbon_offset_kg = sum(
            row["registered_carbon_offset_kg"] for row in renewable_by_type
        )
        annual_consumption_kwh = float(
            annual_consumption_row[0] if annual_consumption_row else 0
        )
        registered_generation_coverage_pct = (
            min(round(registered_generation_kwh / annual_consumption_kwh * 100, 2), 100.0)
            if annual_consumption_kwh > 0
            else 0
        )
        costs_by_currency = []
        for row in energy_cost_rows:
            total_cost = float(row["total_cost"] or 0)
            costed_kwh = float(row["costed_kwh"] or 0)
            costs_by_currency.append({
                "currency_code": row["cost_currency_code"],
                "total_cost": round(total_cost, 2),
                "costed_kwh": round(costed_kwh, 2),
                "effective_cost_per_kwh": round(total_cost / costed_kwh, 4) if costed_kwh > 0 else None,
                "reading_count": int(row["reading_count"] or 0),
            })
        unclassified_cost_reading_count = int(
            unclassified_cost_row[0] if unclassified_cost_row else 0
        )
        comparable_energy_cost = (
            len(costs_by_currency) == 1 and unclassified_cost_reading_count == 0
        )
        monthly_carbon_offset_kg = round(registered_carbon_offset_kg / 12, 2)
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
                "monthly_carbon_offset_kg": monthly_carbon_offset_kg,
                "net_monthly_emissions_kg": round(
                    estimated_emissions_kg - monthly_carbon_offset_kg, 2
                ),
                "by_source_type": emissions_by_source,
            },
            "registered_renewables": {
                "period_days": 365,
                "active_sources": sum(row["source_count"] for row in renewable_by_type),
                "total_capacity_kw": round(registered_capacity_kw, 2),
                "annual_generation_kwh": round(registered_generation_kwh, 2),
                "registered_carbon_offset_kg": round(registered_carbon_offset_kg, 2),
                "annual_verified_consumption_kwh": round(annual_consumption_kwh, 2),
                "legacy_generation_coverage_pct": registered_generation_coverage_pct,
                "by_type": renewable_by_type,
            },
            "trend_7d": [
                {
                    "reading_date": _iso(row["reading_date"]),
                    "consumption_kwh": round(float(row["consumption_kwh"] or 0), 2),
                    "production_kwh": round(float(row["production_kwh"] or 0), 2),
                }
                for row in trend_rows
            ],
            "reviewed_efficiency_history": [
                {
                    "log_date": _iso(row["log_date"]),
                    "period": row["period"],
                    "total_consumption_kwh": (
                        round(float(row["total_consumption_kwh"]), 2)
                        if row["total_consumption_kwh"] is not None
                        else None
                    ),
                    "total_production_kwh": (
                        round(float(row["total_production_kwh"]), 2)
                        if row["total_production_kwh"] is not None
                        else None
                    ),
                    "net_energy_kwh": (
                        round(float(row["net_energy_kwh"]), 2)
                        if row["net_energy_kwh"] is not None
                        else None
                    ),
                    "renewable_pct": (
                        round(float(row["renewable_pct"]), 2)
                        if row["renewable_pct"] is not None
                        else None
                    ),
                    "carbon_intensity_kg_kwh": (
                        round(float(row["carbon_intensity_kg_kwh"]), 4)
                        if row["carbon_intensity_kg_kwh"] is not None
                        else None
                    ),
                }
                for row in efficiency_rows
            ],
            "active_sources_by_type": [
                {
                    "source_type": row["source_type"],
                    "source_count": int(row["source_count"] or 0),
                    "capacity_kw": round(float(row["capacity_kw"] or 0), 2),
                }
                for row in active_source_rows
            ],
            "energy_costs": {
                "period_days": 30,
                "by_currency": costs_by_currency,
                "unclassified_cost_reading_count": unclassified_cost_reading_count,
                "comparable_total": (
                    {
                        "currency_code": costs_by_currency[0]["currency_code"],
                        "total_cost": costs_by_currency[0]["total_cost"],
                        "effective_cost_per_kwh": costs_by_currency[0]["effective_cost_per_kwh"],
                    }
                    if comparable_energy_cost
                    else None
                ),
            },
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
