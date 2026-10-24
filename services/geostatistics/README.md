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

For the `simulate` command, `--mode-no` accepts 1–1,000 GSTools random modes
and defaults to 1,000 to preserve the existing generator setting. Lower values
can reduce runtime on constrained hosts, with a corresponding loss of spectral
fidelity. The selected mode count, generator, sampling mode, and GSTools version
are recorded in each persisted realization's JSONB metadata. Synthetic moment
checks cover the 100-mode setting for spherical and Gaussian models; choose
settings for production only after scientific review against representative
data.
