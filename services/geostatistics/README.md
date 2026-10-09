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
- `simulation` — Geostatistical Simulation — Sequential Gaussian Simulation (SGS).
- `variogram` — Variogram Analysis — empirical variogram computation and model fitting.

## Files

8 Python modules
