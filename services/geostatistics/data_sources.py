"""Fixed, location-scoped source queries for geostatistical properties."""

from __future__ import annotations

SOIL_PROPERTY_COLUMNS = {
    "soil_carbon": "organic_carbon_pct",
    "soil_moisture": "moisture_pct",
    "soil_ph": "ph",
}


def supports_database_property(property_key: object) -> bool:
    """Return whether a property has a fixed point-data source query."""
    return isinstance(property_key, str) and (
        property_key in SOIL_PROPERTY_COLUMNS or property_key == "ndvi"
    )


def location_point_query(location_id: str, property_key: str) -> tuple[str, tuple[str]]:
    """Build the fixed source query for one supported location/property pair."""
    if not supports_database_property(property_key):
        raise ValueError(f"Unsupported property_key: {property_key}")
    if property_key in SOIL_PROPERTY_COLUMNS:
        value_column = SOIL_PROPERTY_COLUMNS[property_key]
        return (
            f"""
            SELECT ss.gps_latitude AS lat, ss.gps_longitude AS lon,
                   ss.{value_column} AS value
              FROM soil_sample ss
             WHERE ss.location_id = %s
               AND ss.gps_latitude IS NOT NULL
               AND ss.gps_longitude IS NOT NULL
               AND ss.{value_column} IS NOT NULL
            """,
            (location_id,),
        )
    if property_key == "ndvi":
        return (
            """
            SELECT ST_Y(rso.centroid) AS lat, ST_X(rso.centroid) AS lon,
                   rso.ndvi AS value
              FROM remote_sensing_observation rso
             WHERE rso.location_id = %s
               AND rso.centroid IS NOT NULL
               AND rso.ndvi IS NOT NULL
            """,
            (location_id,),
        )
    raise ValueError(f"Unsupported property_key: {property_key}")
