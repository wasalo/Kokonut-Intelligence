"""Unified ingestion CLI — lists available ingestion tools and routes to subcommands.

This CLI provides a single entry point for all ingestion pipelines.  Individual
ingestion modules remain fully invocable via their own ``python3 -m
services.ingestion.<module>`` paths.
"""

from __future__ import annotations

import argparse
import importlib
import sys

TOOLS = {
    "sensor_ingester": {
        "module": "services.ingestion.sensor_ingester",
        "help": "Sensor data ingestion (CSV import, single reading, calibration)",
    },
    "weather": {
        "module": "services.ingestion.weather",
        "help": "Current weather observations from OpenWeatherMap",
    },
    "weather_forecast": {
        "module": "services.ingestion.weather_forecast",
        "help": "5-day / 3-hour weather forecast ingestion",
    },
    "climate_data": {
        "module": "services.ingestion.climate_data",
        "help": "WorldClim, NCEP, MODIS, SMAP, Sentinel-1 climate datasets",
    },
    "market_data": {
        "module": "services.ingestion.market_data",
        "help": "Commodity price data from World Bank / Pink Sheets",
    },
    "anomaly_detector": {
        "module": "services.ingestion.anomaly_detector",
        "help": "Sensor anomaly detection and ML training",
    },
    "data_freshness": {
        "module": "services.ingestion.data_freshness",
        "help": "Data freshness monitoring and summary",
    },
    "gis_import": {
        "module": "services.ingestion.gis_import",
        "help": "GIS boundary data import (GeoJSON, CSV)",
    },
    "gnosis_indexer": {
        "module": "services.ingestion.gnosis_indexer",
        "help": "Gnosis Chain Moloch DAO event ingestion",
    },
    "baal_indexer": {
        "module": "services.ingestion.baal_indexer",
        "help": "Kokonut Baal (Moloch v3) DAO event indexing",
    },
    "eas_indexer": {
        "module": "services.ingestion.eas_indexer",
        "help": "EAS attestation ingestion (Optimism, Base, Celo)",
    },
    "remote_sensing": {
        "module": "services.ingestion.remote_sensing",
        "help": "Remote sensing CSV ingestion",
    },
    "remote_sensing_fetcher": {
        "module": "services.ingestion.remote_sensing_fetcher",
        "help": "Remote sensing fetch orchestrator (GEE, Copernicus)",
    },
    "mqtt_subscriber": {
        "module": "services.ingestion.mqtt_subscriber",
        "help": "MQTT sensor subscriber",
    },
    "http_sensor_receiver": {
        "module": "services.ingestion.http_sensor_receiver",
        "help": "HTTP sensor data receiver server",
    },
    "device_manager": {
        "module": "services.ingestion.device_manager",
        "help": "IoT device manager (list, register, health)",
    },
    "price_attestation": {
        "module": "services.ingestion.price_attestation",
        "help": "Commodity price feed attestation",
    },
    "mock_sensors": {
        "module": "services.ingestion.mock_sensors",
        "help": "Mock sensor data generator for testing",
    },
    "status": {
        "module": "services.ingestion.status",
        "help": "Ingestion status monitoring (logs, indexers, summary)",
    },
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="services.ingestion",
        description="Kokonut ingestion pipelines",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available ingestion tools",
    )

    sub = parser.add_subparsers(dest="tool")

    for name, info in TOOLS.items():
        p = sub.add_parser(name, help=info["help"])

    if argv is None:
        argv = sys.argv[1:]

    # If no args or --list, show the tool list
    if not argv or (len(argv) == 1 and argv[0] in ("-h", "--help", "--list")):
        if argv and argv[0] == "--list":
            for name, info in sorted(TOOLS.items()):
                print(f"  {name:<28} {info['help']}")
        else:
            parser.print_help()
            print("\nUse --list to see all available ingestion tools.")
            print("Run a specific tool via:  python3 -m services.ingestion.<tool>")
        return

    # Parse the tool name and forward remaining args
    args, remaining = parser.parse_known_args(argv)
    if not args.tool:
        parser.print_help()
        return

    info = TOOLS[args.tool]
    mod = importlib.import_module(info["module"])

    # Delegate to the module's main(), injecting remaining args
    sys.argv = [f"services.ingestion.{args.tool}"] + remaining
    if hasattr(mod, "main"):
        mod.main()
    else:
        # Fallback: run the module directly
        import runpy

        runpy.run_module(info["module"], run_name="__main__")


if __name__ == "__main__":
    main()
