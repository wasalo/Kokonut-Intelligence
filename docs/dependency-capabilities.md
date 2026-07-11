# Dependency Capabilities

Maps each updated dependency's new features to platform capabilities. This document tracks what each dependency version brings and how it benefits the Kokonut Intelligence platform.

## PostgreSQL 16

| Feature | Platform Benefit |
|---------|-----------------|
| SQL/JSON constructors (`JSON_OBJECT`, `JSON_ARRAY`) | CIDS export queries build JSON payloads in-database; public metric views construct JSON at query level |
| `pg_stat_io` view | I/O performance monitoring for metric computation and CRISP scoring jobs |
| Parallel FULL/outer hash joins | Faster multi-table joins for CRISP scoring, portfolio aggregation, metric computation |
| Parallel `string_agg()` and `array_agg()` | Faster aggregation in seed scripts and metric computation |
| Expression indexes with immutable `date_trunc` | Time-series queries on weather and sensor data |
| `IS JSON` checks | Agent task output validation, attestation metadata validation |
| Logical replication standby | Read-heavy analytics on standby without impacting primary |
| `pg_input_is_valid()` / `pg_input_error_info()` | Data type validation in ingestion pipelines |
| `random_normal()` | Simulation and forecasting models |

## ClickHouse 25.8 LTS

| Feature | Platform Benefit |
|---------|-----------------|
| PromQL dialect | Time-series analytics with PromQL-style queries |
| Iceberg/DeltaLake write | Data lake interoperability with external analytical tools |
| `_table` virtual column | Simplifies UNION ALL queries across sensor/weather/financial tables |
| Correlated subqueries | Complex analytical queries for portfolio and metric computation |
| TimeSeries functions | Time-series resampling and prediction for sensor data |
| Parquet v3 reader | Faster bulk data ingestion from CSV and sensor imports |
| CPU slot preemption | Fair CPU allocation for concurrent metric computation |

## Directus 12.1.1

| Feature | Platform Benefit |
|---------|-----------------|
| Versioned collections locked on publish | Enforces governed lifecycle (draft → published) |
| MCP server improvements | Better AI integration for data queries |
| Interactive Schema Viewer | Easier exploration of 363-table schema |
| Sub-collections in Library | Better organization of 53+ dashboards |
| Alerts Management page | Centralized alert management |
| Programmatic filters | Better partner dashboard integration |

## FastAPI 0.139+

| Feature | Platform Benefit |
|---------|-----------------|
| 2x JSON via Pydantic/Rust | Higher throughput for HTTP sensor receiver |
| Native SSE | Real-time sensor event streaming |
| Streaming JSON Lines | Chunked batch sensor data ingestion |

## Prefect 3.x

| Feature | Platform Benefit |
|---------|-----------------|
| 90% overhead reduction | Much more efficient workflow orchestration |
| Event-driven automations | Replace cron with event-triggered triggers |
| CANCELLING timeout | Prevents zombie pipeline runs |
| MCP server | AI-assisted debugging of workflows |

## numpy 2.x

| Feature | Platform Benefit |
|---------|-----------------|
| SIMD-accelerated sorting | Faster data processing for large datasets |
| StringDType | Better string handling in data pipelines |
| Array API standard | GPU/alternative backend support for ML models |

## pandas 3.0

| Feature | Platform Benefit |
|---------|-----------------|
| Copy-on-Write default | Performance improvement, no code changes needed |
| Arrow PyCapsule Interface | Zero-copy data exchange with analytical tools |
| Anti joins | New query patterns for relational analysis |

## scikit-learn 1.9

| Feature | Platform Benefit |
|---------|-----------------|
| Callback API | Progress bars and monitoring for ML training |
| Array API support | GPU acceleration for linear models |
| SGDOneClassSVM fix | Corrected anomaly detection formulation |
| HistGradientBoosting fix | Better weighted training for carbon prediction |

## Prophet 1.3

| Feature | Platform Benefit |
|---------|-----------------|
| `scaling='minmax'` | Better convergence on bounded sensor ranges (0-100%) |
| Custom CV metrics | Domain-specific evaluation for anomaly detection |
| NaN date handling | Correct processing of missing sensor readings |
| CmdStan upgrade | Faster, more reliable sampling |

## yfinance 1.x

| Feature | Platform Benefit |
|---------|-----------------|
| Authenticated access | Yahoo Finance login for reliable data |
| Consolidated dataframes | Cleaner data handling |
| curl_cffi fallback | Graceful degradation in Docker |
| Thread-safe downloads | Parallel commodity fetching |

## Metabase 0.62.4

| Feature | Platform Benefit |
|---------|-----------------|
| Custom visualizations | Build farm-specific charts |
| MCP server (charts in AI) | AI-integrated data queries |
| Interactive Schema Viewer | Explore 363-table schema |
| Sub-collections | Better dashboard organization |
| Programmatic filters | Enhanced embedded analytics |
