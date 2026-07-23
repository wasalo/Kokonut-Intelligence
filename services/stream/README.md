# stream

`services.stream` — Real-time stream processing for IoT sensor data.

## CLI Usage

```bash
python3 -m services.stream.cli --help
```

## Modules

- `alerts` — Real-time alert evaluation for stream processing.
- `buffer` — Stream buffer — manages backpressure for high-throughput sensor ingestion.
- `cli` — CLI for the stream processor.
- `processor` — Stream processor — ingests, aggregates, and detects anomalies in real-time sensor data.
- `windows` — Windowed aggregation for stream processing — tumbling and sliding windows.

## Files

5 Python modules
