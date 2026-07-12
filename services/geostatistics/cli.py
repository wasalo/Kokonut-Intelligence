"""
Geostatistics Suite

Usage:
    python3 -m services.geostatistics --help
    python3 -m services.geostatistics variogram --location-id UUID --property soil_carbon
    python3 -m services.geostatistics kriging --location-id UUID --property soil_carbon --method ordinary --resolution 10
    python3 -m services.geostatistics simulate --location-id UUID --property soil_carbon --realizations 100
    python3 -m services.geostatistics autocorrelation --location-id UUID --property soil_carbon --weights queen
    python3 -m services.geostatistics cross-validate --location-id UUID --property soil_carbon --strategy spatial_block --block-size 200
    python3 -m services.geostatistics sensor-design --location-id UUID --property soil_moisture
    python3 -m services.geostatistics residual-kriging --location-id UUID
    python3 -m services.geostatistics spatial-cv-soc --location-id UUID --block-size 200
    python3 -m services.geostatistics --json
"""

from __future__ import annotations

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Kokonut Geostatistics Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    sub = parser.add_subparsers(dest="command")

    # variogram
    vg = sub.add_parser("variogram", help="Fit variogram model to point data")
    vg.add_argument("--location-id", required=True, help="Location UUID")
    vg.add_argument("--property", required=True, dest="property_key",
                    help="Property key (soil_carbon, soil_moisture, soil_ph, ndvi)")
    vg.add_argument("--model", default=None,
                    help="Variogram model type (spherical, exponential, gaussian, matern)")
    vg.add_argument("--lag-distance", type=float, default=None, help="Lag distance in meters")
    vg.add_argument("--persist", action="store_true", help="Persist to database")

    # kriging
    kr = sub.add_parser("kriging", help="Run kriging interpolation")
    kr.add_argument("--location-id", required=True, help="Location UUID")
    kr.add_argument("--property", required=True, dest="property_key")
    kr.add_argument("--method", default="ordinary",
                    help="Kriging method (ordinary, simple, indicator)")
    kr.add_argument("--resolution", type=float, default=10.0, help="Grid resolution in meters")
    kr.add_argument("--variogram-id", default=None, help="Variogram model UUID to use")
    kr.add_argument("--threshold", type=float, default=None, help="Threshold for indicator kriging")
    kr.add_argument("--persist", action="store_true", help="Persist to database")

    # simulate
    sim = sub.add_parser("simulate", help="Sequential Gaussian Simulation")
    sim.add_argument("--location-id", required=True, help="Location UUID")
    sim.add_argument("--property", required=True, dest="property_key")
    sim.add_argument("--realizations", type=int, default=100, help="Number of realizations")
    sim.add_argument("--resolution", type=float, default=10.0, help="Grid resolution in meters")
    sim.add_argument("--seed", type=int, default=42, help="Random seed")
    sim.add_argument("--variogram-id", default=None, help="Variogram model UUID")
    sim.add_argument("--persist", action="store_true", help="Persist to database")

    # autocorrelation
    ac = sub.add_parser("autocorrelation", help="Spatial autocorrelation (Moran's I, Geary's C)")
    ac.add_argument("--location-id", required=True, help="Location UUID")
    ac.add_argument("--property", required=True, dest="property_key")
    ac.add_argument("--weights", default="queen",
                    help="Spatial weights type (queen, rook, distance, knn)")
    ac.add_argument("--distance", type=float, default=500.0, help="Distance threshold for weights")
    ac.add_argument("--k-neighbors", type=int, default=8, help="K for KNN weights")
    ac.add_argument("--persist", action="store_true", help="Persist to database")

    # cross-validate
    cv = sub.add_parser("cross-validate", help="Spatial cross-validation")
    cv.add_argument("--location-id", required=True, help="Location UUID")
    cv.add_argument("--property", required=True, dest="property_key")
    cv.add_argument("--strategy", default="spatial_block",
                    help="CV strategy (spatial_block, leave_one_out)")
    cv.add_argument("--block-size", type=float, default=200.0, help="Block size for spatial_block CV")
    cv.add_argument("--variogram-id", default=None, help="Variogram model UUID")
    cv.add_argument("--persist", action="store_true", help="Persist to database")

    # sensor-design
    sd = sub.add_parser("sensor-design", help="Optimal sensor network design")
    sd.add_argument("--location-id", required=True, help="Location UUID")
    sd.add_argument("--property", default="soil_moisture", dest="property_key")
    sd.add_argument("--persist", action="store_true", help="Persist to database")

    # residual-kriging (SOC enhancement)
    rk = sub.add_parser("residual-kriging", help="Residual kriging correction for SOC prediction")
    rk.add_argument("--location-id", required=True, help="Location UUID")

    # spatial-cv-soc (SOC enhancement)
    sc = sub.add_parser("spatial-cv-soc", help="Spatial block CV for SOC model")
    sc.add_argument("--location-id", required=True, help="Location UUID")
    sc.add_argument("--block-size", type=float, default=200.0, help="Block size in meters")
    sc.add_argument("--persist", action="store_true", help="Persist to cv_fold_result")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    from services.ingestion.base import get_db

    conn = get_db()

    try:
        if args.command == "variogram":
            from .variogram import VariogramAnalyzer
            va = VariogramAnalyzer(conn=conn)
            result = va.fit_from_db(
                args.location_id,
                args.property_key,
                model_type=args.model,
                lag_distance=args.lag_distance,
            )
            if args.persist and "error" not in result:
                model_id = va.persist_variogram(
                    args.location_id, args.property_key, result
                )
                result["persisted_id"] = model_id

        elif args.command == "kriging":
            from .kriging import KrigingEngine
            ke = KrigingEngine(conn=conn)
            result = ke.kriging_from_db(
                args.location_id,
                args.property_key,
                method=args.method,
                resolution_m=args.resolution,
                variogram_model_id=args.variogram_id,
                threshold=args.threshold,
            )
            if args.persist and "error" not in result:
                # Need variogram_model_id for persistence
                vm_id = args.variogram_id or result.get("variogram_model_id")
                if vm_id:
                    pred_id = ke.persist_kriging(
                        args.location_id, args.property_key, vm_id, result
                    )
                    result["persisted_prediction_id"] = pred_id

        elif args.command == "simulate":
            from .simulation import GeostatSimulator
            gs = GeostatSimulator(conn=conn)
            result = gs.simulation_from_db(
                args.location_id,
                args.property_key,
                n_realizations=args.realizations,
                grid_resolution_m=args.resolution,
                seed=args.seed,
                variogram_model_id=args.variogram_id,
            )
            if args.persist and "error" not in result:
                vm_id = args.variogram_id or result.get("variogram_model_id")
                if vm_id:
                    real_id = gs.persist_simulations(
                        args.location_id, args.property_key, vm_id, result
                    )
                    result["persisted_realization_id"] = real_id
            # Don't print full realizations
            if "realizations" in result:
                result["realizations"] = f"[{result['n_realizations']} realizations]"

        elif args.command == "autocorrelation":
            from .autocorrelation import SpatialAutocorrelation
            sa = SpatialAutocorrelation(conn=conn)
            result = sa.autocorrelation_from_db(
                args.location_id,
                args.property_key,
                weights_type=args.weights,
                distance_threshold=args.distance,
                k_neighbors=args.k_neighbors,
            )
            if args.persist and "error" not in result:
                ids = sa.persist_results(
                    args.location_id, args.property_key, result
                )
                result["persisted_ids"] = ids

        elif args.command == "cross-validate":
            from .cross_validation import SpatialCrossValidator
            scv = SpatialCrossValidator(conn=conn)
            result = scv.cross_validate_from_db(
                args.location_id,
                args.property_key,
                cv_strategy=args.strategy,
                block_size_m=args.block_size,
                variogram_model_id=args.variogram_id,
            )
            if args.persist and "error" not in result:
                vm_id = args.variogram_id or result.get("variogram_model_id")
                record_id = scv.persist_cv_results(
                    args.location_id, args.property_key, vm_id, result
                )
                result["persisted_cv_id"] = record_id

        elif args.command == "sensor-design":
            from .sensor_optimization import SensorNetworkDesigner
            snd = SensorNetworkDesigner(conn=conn)
            result = snd.design_from_db(args.location_id, args.property_key)
            if args.persist and "error" not in result:
                record_id = snd.persist_design(
                    args.location_id, args.property_key, result
                )
                result["persisted_design_id"] = record_id

        elif args.command == "residual-kriging":
            from services.analytics.soc_prediction import residual_kriging_correction
            result = residual_kriging_correction(conn, args.location_id)

        elif args.command == "spatial-cv-soc":
            from services.analytics.soc_prediction import spatial_block_cv_for_soc
            result = spatial_block_cv_for_soc(conn, args.location_id, args.block_size)
            if args.persist and "error" not in result:
                result["persisted"] = True

        else:
            parser.print_help()
            return

        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            _print_result(args.command, result)

    finally:
        conn.close()


def _print_result(command: str, result: dict):
    """Pretty-print results for each command."""
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return

    if command == "variogram":
        print(f"Variogram Model Fitted")
        print(f"  Property:    {result.get('property_key', 'N/A')}")
        print(f"  Model type:  {result.get('model_type', 'N/A')}")
        print(f"  Sill:        {result.get('sill', 'N/A'):.4f}")
        print(f"  Range:       {result.get('range', 'N/A'):.2f} m")
        print(f"  Nugget:      {result.get('nugget', 'N/A'):.4f}")
        print(f"  R-squared:   {result.get('r_squared', 'N/A')}")
        print(f"  Samples:     {result.get('n_samples', 'N/A')}")
        if "persisted_id" in result:
            print(f"  Persisted:   {result['persisted_id']}")

    elif command == "kriging":
        print(f"Kriging Interpolation")
        print(f"  Property:    {result.get('property_key', 'N/A')}")
        print(f"  Method:      {result.get('method', 'N/A')}")
        print(f"  Points:      {result.get('n_points', 'N/A')}")
        print(f"  Resolution:  {result.get('resolution_m', 'N/A')} m")
        if "persisted_prediction_id" in result:
            print(f"  Persisted:   {result['persisted_prediction_id']}")

    elif command == "simulate":
        print(f"Sequential Gaussian Simulation")
        print(f"  Property:       {result.get('property_key', 'N/A')}")
        print(f"  Realizations:   {result.get('n_realizations', 'N/A')}")
        print(f"  Grid points:    {result.get('n_points', 'N/A')}")
        print(f"  Grid res:       {result.get('grid_resolution_m', 'N/A')} m")
        print(f"  E-type range:   {min(result.get('e_type', [0])):.3f} - {max(result.get('e_type', [0])):.3f}")
        if "persisted_realization_id" in result:
            print(f"  Persisted:      {result['persisted_realization_id']}")

    elif command == "autocorrelation":
        mi = result.get("morans_i", {})
        gc = result.get("gearys_c", {})
        print(f"Spatial Autocorrelation")
        print(f"  Property:    {result.get('property_key', 'N/A')}")
        print(f"  Samples:     {result.get('n_samples', 'N/A')}")
        print(f"  Moran's I:   {mi.get('statistic_value', 'N/A')} (p={mi.get('p_value', 'N/A')}, {mi.get('interpretation', 'N/A')})")
        print(f"  Geary's C:   {gc.get('statistic_value', 'N/A')} (p={gc.get('p_value', 'N/A')}, {gc.get('interpretation', 'N/A')})")
        if "persisted_ids" in result:
            print(f"  Persisted:   {result['persisted_ids']}")

    elif command == "cross-validate":
        print(f"Spatial Cross-Validation")
        print(f"  Strategy:    {result.get('cv_strategy', 'N/A')}")
        print(f"  Folds:       {result.get('n_folds', 'N/A')} ({result.get('n_successful_folds', 'N/A')} successful)")
        print(f"  RMSE:        {result.get('root_mean_squared_error', 'N/A')}")
        print(f"  MAE:         {result.get('mean_absolute_error', 'N/A')}")
        print(f"  R-squared:   {result.get('r_squared', 'N/A')}")
        print(f"  Mean error:  {result.get('mean_error', 'N/A')} (bias)")
        if "persisted_cv_id" in result:
            print(f"  Persisted:   {result['persisted_cv_id']}")

    elif command == "sensor-design":
        print(f"Sensor Network Design")
        print(f"  Property:    {result.get('property_key', 'N/A')}")
        print(f"  Range:       {result.get('variogram_range_m', 'N/A')} m")
        print(f"  Optimal:     {result.get('optimal_spacing_m', 'N/A')} m spacing")
        print(f"  Current:     {result.get('current_n_sensors', 'N/A')} sensors")
        print(f"  Recommended: {result.get('recommended_n_sensors', 'N/A')} sensors")
        print(f"  Coverage:    {100 - result.get('coverage_gap_pct', 0):.1f}% covered")
        for rec in result.get("recommendations", []):
            print(f"  → {rec}")
        if "persisted_design_id" in result:
            print(f"  Persisted:   {result['persisted_design_id']}")

    elif command in ("residual-kriging", "spatial-cv-soc"):
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
