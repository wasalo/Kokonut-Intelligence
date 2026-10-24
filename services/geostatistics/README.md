# geostatistics

`services.geostatistics` — Geostatistics suite: variogram modeling, kriging, simulation,

## CLI Usage

```bash
python3 -m services.geostatistics.cli --help
```

## Modules

- `autocorrelation` — Spatial Autocorrelation — Moran's I, Geary's C.
- `cli` — Geostatistics Suite
- `config` — Shared constants and configuration for geostatistics.
- `cross_validation` — Spatial Cross-Validation — block CV, leave-one-out, k-fold.
- `kriging` — Kriging Engine — Ordinary, Simple, and Indicator kriging.
- `sensor_optimization` — Sensor Network Design — optimal spacing from variogram parameters.
- `simulation` — Seeded GSTools `CondSRF` realizations, bounded to 100,000 grid points, 1,000 realizations, and 1,000,000 output values; local-meter results are converted back to WGS84 before geometry persistence. Legacy function/CLI names remain available.
- `variogram` — Variogram Analysis — empirical variogram computation and model fitting.

## Files

8 Python modules
