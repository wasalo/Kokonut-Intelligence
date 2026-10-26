"""Argument contracts for database-driven scheduler commands.

Module allowlisting prevents arbitrary imports. These schemas additionally
limit which supported command a persisted task may invoke and validate its
arguments before activation or process creation.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from uuid import UUID

from services.security.execution_allowlist import (
    ALLOWED_SCHEDULED_MODULES,
    validate_scheduled_module,
)

# Celo is Kokonut's primary EAS chain. The remaining supported networks stay
# available as explicit, separately scoped indexing operations.
EAS_SCHEDULE_CHAINS = ("celo", "optimism", "base")
RPC_SCHEDULE_CHAINS = (
    "ethereum",
    "optimism",
    "base",
    "arbitrum",
    "celo",
    "celo-alfajores",
    "gnosis",
)


class ScheduledCommandRejected(ValueError):
    """A scheduled command violates its module-specific operation contract."""


_OPTIONS: dict[str, dict[str, str | None]] = {
    "services.ingestion.weather": {"--location-id": "uuid"},
    # New native plans use the dedicated signed worker. The shared-identity
    # module remains available only for previously persisted tasks.
    "services.ingestion.weather_worker": {"--location-id": "uuid"},
    # Legacy persisted rows stay operable until schedule owners reconcile them.
    "services.ingestion.weather_forecast_worker": {"--location-id": "uuid"},
    "services.ingestion.weather_forecast": {"--location-id": "uuid"},
    "services.ingestion.market_data": {
        "--commodity": "commodity",
        "--source": "market_source",
        "--month": "month",
        "--year": "year",
    },
    "services.ingestion.market_data_worker": {
        "--commodity": "commodity",
        "--month": "month",
        "--year": "year",
    },
    "services.ingestion.eas_indexer": {"--chain": "eas_chain"},
    "services.ingestion.eas_worker": {"--chain": "eas_chain"},
    "services.ingestion.rpc_indexer": {
        "--chain": "rpc_chain",
        "--wallet": "wallet",
    },
    "services.ingestion.rpc_worker": {"--chain": "rpc_chain"},
    # Scheduled sensor ingestion resolves a registered, enabled, location-bound
    # pull driver instance from PostgreSQL. Arbitrary file paths and payloads
    # never come from persisted task arguments.
    "services.ingestion.sensor_ingester": {
        "--driver-instance-id": "uuid",
        "--location-id": "uuid",
    },
    "services.ingestion.sensor_worker": {
        "--driver-instance-id": "uuid",
        "--location-id": "uuid",
    },
    "services.ingestion.gnosis_indexer": {
        "--from-block": "block",
        "--to-block": "block",
    },
    "services.ingestion.gnosis_worker": {
        "--from-block": "block",
        "--to-block": "block",
    },
    "services.ingestion.baal_indexer": {
        "--from-block": "block",
        "--to-block": "block",
    },
    "services.ingestion.baal_worker": {
        "--from-block": "block",
        "--to-block": "block",
    },
    "services.ingestion.anomaly_detector": {
        "--sensor": "uuid",
        "--since": "datetime",
        "--baseline-check": None,
        "--location-id": "uuid",
    },
    "services.metrics": {
        "--compute": None,
        "--metric": "metric_key",
        "--all": None,
        "--location-id": "uuid",
        "--period-start": "date",
        "--period-end": "date",
        "--json": None,
    },
    "services.metrics.noi_snapshot_worker": {"--location-id": "uuid"},
    "services.analytics.carbon_credit_adjustment_worker": {"--location-id": "uuid"},
    "services.ingestion.data_freshness": {
        "--check": None,
        "--source": "identifier",
    },
    "services.ingestion.freshness_worker": {
        "--check": None,
        "--source": "identifier",
    },
    "services.export.dataset_refresh": {
        "--dataset-id": "uuid",
        "--all": None,
    },
    "services.ingestion.climate_data": {
        "--worldclim": None,
        "--ncep": None,
        "--modis": None,
        "--smap": None,
        "--sentinel1": None,
        "--all": None,
        "--location-id": "uuid",
    },
    "services.ingestion.climate_worker": {"--location-id": "uuid"},
    "services.events": {
        "--process": None,
        "--notification-process": None,
        "--batch-size": "batch_size",
    },
    # This dedicated entrypoint only recomputes and reports differences. The
    # interactive issuance/retirement CLI is intentionally not schedulable.
    "services.analytics.carbon_credit_adjustment_check": {
        "--location-id": "uuid",
    },
    "services.ingestion.remote_sensing_fetcher": {
        "--run-jobs": None,
        "--limit": "small_batch_size",
        "--location-id": "uuid",
    },
    "services.ingestion.remote_sensing_worker": {
        "--limit": "small_batch_size",
        "--location-id": "uuid",
    },
    "services.ingestion.clickhouse_outbox": {
        "--run-once": None,
        "--limit": "batch_size",
    },
}

if frozenset(_OPTIONS) != ALLOWED_SCHEDULED_MODULES:
    raise RuntimeError("Scheduled command contracts must cover the module allowlist exactly")


def _reject(message: str) -> ScheduledCommandRejected:
    return ScheduledCommandRejected(message)


def _validate_value(kind: str, value: str) -> None:
    if not value or len(value) > 512 or "\x00" in value:
        raise _reject("argument value is empty, too long, or contains a NUL byte")
    if kind == "uuid":
        try:
            UUID(value)
        except (ValueError, AttributeError):
            raise _reject("location, sensor, and dataset IDs must be UUIDs") from None
    elif kind == "market_source":
        if value not in {"world_bank", "seed"}:
            raise _reject("market data source is not supported")
    elif kind == "eas_chain":
        if value not in EAS_SCHEDULE_CHAINS:
            raise _reject("EAS chain is not supported")
    elif kind == "rpc_chain":
        if value not in RPC_SCHEDULE_CHAINS:
            raise _reject("RPC chain is not supported")
    elif kind == "wallet":
        if not re.fullmatch(r"0x[a-fA-F0-9]{40}", value):
            raise _reject("wallet must be a 20-byte hexadecimal address")
    elif kind == "commodity":
        if value.upper() not in {
            "COFFEE", "COCOA", "PALM_OIL", "RICE", "MAIZE", "SUGAR", "TEA", "BANANA"
        }:
            raise _reject("commodity code is not supported")
    elif kind == "metric_key":
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value):
            raise _reject("metric key has an invalid format")
    elif kind == "identifier":
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
            raise _reject("source identifier has an invalid format")
    elif kind in {"month", "year", "block", "batch_size", "small_batch_size"}:
        if not value.isdecimal():
            raise _reject("numeric argument must be a non-negative integer")
        number = int(value)
        limits = {
            "month": (1, 12),
            "year": (1960, 2030),
            "block": (0, 2**63 - 1),
            "batch_size": (1, 1000),
            "small_batch_size": (1, 10),
        }
        lower, upper = limits[kind]
        if not lower <= number <= upper:
            raise _reject("numeric argument is outside its supported range")
    elif kind == "date":
        try:
            date.fromisoformat(value)
        except ValueError:
            raise _reject("period dates must use YYYY-MM-DD") from None
    elif kind == "datetime":
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise _reject("since must be an ISO-8601 datetime") from None
    else:
        raise RuntimeError(f"Unknown scheduled argument value type: {kind}")


def _validate_operation(module_path: str, values: dict[str, str | bool]) -> None:
    options = set(values)

    if module_path == "services.ingestion.sensor_ingester":
        if options != {"--driver-instance-id", "--location-id"}:
            raise _reject(
                "scheduled sensor ingestion requires one driver instance and one location"
            )
    if module_path == "services.ingestion.sensor_worker":
        if options != {"--driver-instance-id", "--location-id"}:
            raise _reject(
                "scheduled sensor ingestion requires one driver instance and one location"
            )

    if module_path in {
        "services.ingestion.weather",
        "services.ingestion.weather_worker",
    } and "--location-id" not in options:
        raise _reject("weather ingestion requires one explicit location")

    if module_path == "services.ingestion.weather_worker" and options != {"--location-id"}:
        raise _reject("signed current-weather ingestion accepts one location only")

    if module_path == "services.ingestion.remote_sensing_worker":
        if "--location-id" not in options:
            raise _reject("signed remote-sensing ingestion requires one explicit location")
        if options - {"--location-id", "--limit"}:
            raise _reject("signed remote-sensing ingestion accepts one location and an optional bounded limit")

    if module_path in {"services.ingestion.eas_indexer", "services.ingestion.eas_worker"} and options != {"--chain"}:
        raise _reject("scheduled EAS indexing requires one explicit chain")

    if module_path == "services.ingestion.rpc_indexer":
        if "--chain" not in options:
            raise _reject("scheduled RPC indexing requires one explicit chain")
        if options - {"--chain", "--wallet"}:
            raise _reject("scheduled RPC indexing accepts only one chain and an optional wallet")

    if module_path == "services.ingestion.rpc_worker" and options != {"--chain"}:
        raise _reject("isolated scheduled RPC indexing requires one explicit chain")

    if module_path in {
        "services.ingestion.weather_forecast",
        "services.ingestion.weather_forecast_worker",
    } and options != {"--location-id"}:
        raise _reject("weather forecast ingestion requires one explicit location")

    if module_path in {
        "services.ingestion.market_data",
        "services.ingestion.market_data_worker",
    }:
        has_month = "--month" in options
        has_year = "--year" in options
        if has_month != has_year:
            raise _reject("market-data month and year must be supplied together")
        if (
            module_path == "services.ingestion.market_data"
            and has_month
            and values.get("--source", "world_bank") != "world_bank"
        ):
            raise _reject("month and year filtering is only valid for world_bank")

    elif module_path in {
        "services.ingestion.gnosis_indexer",
        "services.ingestion.gnosis_worker",
    }:
        has_start = "--from-block" in options
        has_end = "--to-block" in options
        if has_start != has_end:
            raise _reject("Gnosis block range requires both --from-block and --to-block")
        if has_start and int(str(values["--from-block"])) > int(str(values["--to-block"])):
            raise _reject("Gnosis block range start must not exceed its end")

    elif module_path in {
        "services.ingestion.baal_indexer",
        "services.ingestion.baal_worker",
    }:
        has_start = "--from-block" in options
        has_end = "--to-block" in options
        if has_start != has_end:
            raise _reject("Baal block range requires both --from-block and --to-block")
        if has_start and int(str(values["--from-block"])) > int(str(values["--to-block"])):
            raise _reject("Baal block range start must not exceed its end")

    elif module_path == "services.ingestion.anomaly_detector":
        if "--location-id" not in options:
            raise _reject("scheduled anomaly detection requires one explicit location")
        if "--baseline-check" in options and options != {"--baseline-check", "--location-id"}:
            raise _reject("baseline check cannot be combined with sensor-window options")

    elif module_path == "services.metrics":
        if "--compute" not in options:
            raise _reject("scheduled metric operation requires --compute")
        all_metrics = "--all" in options
        one_metric = "--metric" in options
        if sum((all_metrics, one_metric)) != 1:
            raise _reject("scheduled compute requires exactly one of --all or --metric")
        if "--location-id" not in options:
            raise _reject("scheduled metric computation requires one explicit location")
        if all_metrics and one_metric:
            raise _reject("--all and --metric are mutually exclusive")
        if "--period-start" in options and "--period-end" in options:
            if date.fromisoformat(str(values["--period-start"])) > date.fromisoformat(str(values["--period-end"])):
                raise _reject("period start must not exceed period end")

    elif module_path == "services.metrics.noi_snapshot_worker":
        if options != {"--location-id"}:
            raise _reject("scheduled NOI snapshot reconciliation requires one explicit location")

    elif module_path == "services.ingestion.data_freshness":
        if "--check" not in options:
            raise _reject("scheduled freshness operation requires --check")

    elif module_path == "services.export.dataset_refresh":
        if ("--all" in options) == ("--dataset-id" in options):
            raise _reject("dataset refresh requires exactly one of --all or --dataset-id")

    elif module_path == "services.ingestion.climate_data":
        providers = options & {"--worldclim", "--ncep", "--modis", "--smap", "--sentinel1", "--all"}
        if "--location-id" not in options:
            raise _reject("climate refresh requires --location-id")
        if len(providers) != 1:
            raise _reject("climate refresh requires exactly one provider or --all")

    elif module_path == "services.ingestion.climate_worker":
        if options != {"--location-id"}:
            raise _reject("signed climate ingestion requires one explicit location")

    elif module_path == "services.events":
        operations = options & {"--process", "--notification-process"}
        if len(operations) != 1:
            raise _reject("scheduled event command must select --process or --notification-process")

    elif module_path == "services.analytics.carbon_credit_adjustment_check":
        if "--location-id" not in options:
            raise _reject("scheduled carbon-credit check requires one explicit location")

    elif module_path == "services.analytics.carbon_credit_adjustment_worker":
        if options != {"--location-id"}:
            raise _reject("signed carbon-credit check requires one explicit location")

    elif module_path == "services.ingestion.remote_sensing_fetcher":
        if "--run-jobs" not in options:
            raise _reject("scheduled remote-sensing operation must run due jobs")
        if "--location-id" not in options:
            raise _reject("scheduled remote-sensing operation requires one explicit location")

    elif module_path == "services.ingestion.clickhouse_outbox":
        if "--run-once" not in options:
            raise _reject("scheduled projection operation must use one bounded delivery batch")


def validate_scheduled_command(module_path: str, command_args: object) -> tuple[str, ...]:
    """Validate and return immutable argv tokens for one scheduled operation.

    Unsupported commands include human-review actions, event cleanup without a
    retention decision, and unbounded event workers. Sensor ingestion accepts
    only an explicit location and registered driver-instance identity;
    validation never invokes the target module.
    """
    try:
        validate_scheduled_module(module_path)
    except (TypeError, ValueError):
        raise _reject("scheduled module is not allowlisted") from None

    if not isinstance(command_args, list):
        raise _reject("command arguments must be a JSON array of strings")
    if len(command_args) > 32:
        raise _reject("command contains too many arguments")

    schema = _OPTIONS[module_path]
    values: dict[str, str | bool] = {}
    index = 0
    total_chars = 0
    while index < len(command_args):
        option = command_args[index]
        if not isinstance(option, str) or len(option) > 128 or "\x00" in option:
            raise _reject("command option token is malformed")
        if option not in schema:
            raise _reject("command contains an unsupported option")
        if option in values:
            raise _reject("command repeats an option")
        value_kind = schema[option]
        if value_kind is None:
            values[option] = True
            total_chars += len(option)
            index += 1
            continue
        index += 1
        if index >= len(command_args):
            raise _reject("command option is missing its value")
        value = command_args[index]
        if not isinstance(value, str) or value.startswith("--"):
            raise _reject("command option value is malformed")
        _validate_value(value_kind, value)
        values[option] = value
        total_chars += len(option) + len(value)
        index += 1
    if total_chars > 4096:
        raise _reject("command arguments exceed the supported size")

    _validate_operation(module_path, values)
    return tuple(command_args)
