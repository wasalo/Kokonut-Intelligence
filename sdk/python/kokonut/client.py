from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from .methods import (
    AssessmentChildReadMethods,
    AssessmentLocationReadMethods,
    AttestationMethods,
    CausalLinkReadMethods,
    CropCycleMethods,
    ExpenseEventMethods,
    ExportMethods,
    FarmMethods,
    FieldNoteMethods,
    ForecastAccuracyReadMethods,
    GeostatRealizationPointReadMethods,
    HarvestEventMethods,
    KrigingPointReadMethods,
    LaborEventMethods,
    LocationMethods,
    LocationReadMethods,
    LossEventMethods,
    NoiMethods,
    PlotMethods,
    ReferenceReadMethods,
    ReportMethods,
    SalesEventMethods,
    SensorReadingMethods,
    WalletProfileMethods,
)
from .types import (
    AssessmentDimension,
    AssessmentSignal,
    AttestationSchema,
    BufferZone,
    BuyerDemandSignal,
    BuyerSegment,
    CarbonCredit,
    CashFlowSnapshot,
    CausalLink,
    CausalLoop,
    ChangePoint,
    CreditAdjustment,
    CreditRetirement,
    CreditTransfer,
    CrispCarbonYieldRisk,
    CrispClimateRisk,
    CrispFinancialRisk,
    CrispImplementationRisk,
    CrispPolicyRisk,
    CrispRiskAssessment,
    Crop,
    DemandForecast,
    DemandTrend,
    EnvironmentalBaseline,
    FarmTask,
    FinancialTransaction,
    ForecastAccuracy,
    ForecastOutput,
    ForecastScenario,
    GeostatCVResult,
    GeostatRealization,
    GeostatRealizationPoint,
    HarvestHandlingRecord,
    InfrastructureAsset,
    KrigingPoint,
    KrigingPrediction,
    LeverageAssessment,
    ListOptions,
    MarketSizeEstimate,
    MetricValue,
    MrvClaim,
    OodaCycleLog,
    OrganicCertificationRecord,
    OrganicComplianceChecklist,
    OrganicInputAudit,
    OrganicReadinessAssessment,
    OrganicTransitionPlan,
    PriceObservation,
    ProductionMarketMatch,
    ProhibitedSubstanceRecord,
    Protocol,
    RemoteSensingObservation,
    SeasonalDecomposition,
    SensorAlert,
    SensorDevice,
    SensorNetworkDesign,
    SensorType,
    SituationAssessment,
    SoilCarbonMeasurement,
    SoilSample,
    SpatialAutocorrelation,
    SpeciesObservation,
    StockFlowModel,
    StockFlowRun,
    StructuralAssumption,
    SystemArchetype,
    SystemVariable,
    TimeDelay,
    TimeSeriesForecast,
    TrendDashboardMetric,
    TrendEstimate,
    TrendSmoothing,
    ValueFlowEvent,
    VariogramModel,
    WeatherObservation,
)

_READ_ONLY_PROJECTION_COLLECTIONS = frozenset(
    {"attestation_record", "export_log", "noi_snapshot", "report_snapshot"}
)


class KokonutError(Exception):
    """Base error for Kokonut SDK."""

    def __init__(self, message: str, status_code: int = 0, response: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AuthenticationError(KokonutError):
    """Raised on 401 / authentication failures."""


class NotFoundError(KokonutError):
    """Raised on 404 responses."""


class ForbiddenError(KokonutError):
    """Raised on 403 responses."""


class ValidationError(KokonutError):
    """Raised on 400 / validation failures."""


class KokonutClient:
    """Python SDK client for the Kokonut Intelligence Platform (Directus-backed).

    Usage::

        client = KokonutClient("http://localhost:8055", token="...")
        # or
        client = KokonutClient("http://localhost:8055")
        client.login("email", "password")

        locations = client.locations.list()
        farms = client.farms.list_by_location(location_id)
    """

    def __init__(self, base_url: str, token: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

        # Typed convenience accessors
        self.locations = LocationMethods(self)
        self.farms = FarmMethods(self)
        self.plots = PlotMethods(self)
        self.crop_cycles = CropCycleMethods(self)
        self.harvest_events = HarvestEventMethods(self)
        self.sales_events = SalesEventMethods(self)
        self.expense_events = ExpenseEventMethods(self)
        self.loss_events = LossEventMethods(self)
        self.labor_events = LaborEventMethods(self)
        self.field_notes = FieldNoteMethods(self)
        self.sensor_readings = SensorReadingMethods(self)
        self.sensor_devices: LocationReadMethods[SensorDevice] = LocationReadMethods(
            self, "sensor_device"
        )
        self.sensor_alerts: LocationReadMethods[SensorAlert] = LocationReadMethods(
            self, "sensor_alert"
        )
        self.wallet_profiles = WalletProfileMethods(self)
        self.attestations = AttestationMethods(self)
        self.reports = ReportMethods(self)
        self.exports = ExportMethods(self)
        self.noi = NoiMethods(self)
        self.carbon_credits: LocationReadMethods[CarbonCredit] = LocationReadMethods(
            self, "carbon_credit"
        )
        self.credit_adjustments: LocationReadMethods[CreditAdjustment] = LocationReadMethods(
            self, "credit_adjustment"
        )
        self.credit_retirements: LocationReadMethods[CreditRetirement] = LocationReadMethods(
            self, "credit_retirement"
        )
        self.credit_transfers: LocationReadMethods[CreditTransfer] = LocationReadMethods(
            self, "credit_transfer"
        )
        self.financial_transactions: LocationReadMethods[FinancialTransaction] = LocationReadMethods(
            self, "financial_transaction"
        )
        self.cash_flow_snapshots: LocationReadMethods[CashFlowSnapshot] = LocationReadMethods(
            self, "cash_flow_snapshot"
        )
        self.weather_observations: LocationReadMethods[WeatherObservation] = LocationReadMethods(
            self, "weather_observation"
        )
        self.soil_samples: LocationReadMethods[SoilSample] = LocationReadMethods(
            self, "soil_sample"
        )
        self.soil_carbon_measurements: LocationReadMethods[SoilCarbonMeasurement] = LocationReadMethods(
            self, "soil_carbon_measurement"
        )
        self.environmental_baselines: LocationReadMethods[EnvironmentalBaseline] = LocationReadMethods(
            self, "environmental_baseline"
        )
        self.species_observations: LocationReadMethods[SpeciesObservation] = LocationReadMethods(
            self, "species_observation"
        )
        self.remote_sensing_observations: LocationReadMethods[RemoteSensingObservation] = LocationReadMethods(
            self, "remote_sensing_observation"
        )
        self.mrv_claims: LocationReadMethods[MrvClaim] = LocationReadMethods(self, "mrv_claim")
        self.metric_values: LocationReadMethods[MetricValue] = LocationReadMethods(
            self, "metric_value"
        )
        self.forecast_scenarios: LocationReadMethods[ForecastScenario] = LocationReadMethods(
            self, "forecast_scenario"
        )
        self.forecast_outputs: LocationReadMethods[ForecastOutput] = LocationReadMethods(
            self, "forecast_output"
        )
        self.time_series_forecasts: LocationReadMethods[TimeSeriesForecast] = LocationReadMethods(
            self, "time_series_forecast"
        )
        self.forecast_accuracies: ForecastAccuracyReadMethods[ForecastAccuracy] = (
            ForecastAccuracyReadMethods(self)
        )
        self.variogram_models: LocationReadMethods[VariogramModel] = LocationReadMethods(
            self, "variogram_model"
        )
        self.kriging_predictions: LocationReadMethods[KrigingPrediction] = LocationReadMethods(
            self, "kriging_prediction"
        )
        self.kriging_points: KrigingPointReadMethods[KrigingPoint] = KrigingPointReadMethods(
            self
        )
        self.geostat_realizations: LocationReadMethods[GeostatRealization] = LocationReadMethods(
            self, "geostat_realization"
        )
        self.geostat_realization_points: GeostatRealizationPointReadMethods[
            GeostatRealizationPoint
        ] = GeostatRealizationPointReadMethods(self)
        self.spatial_autocorrelations: LocationReadMethods[SpatialAutocorrelation] = (
            LocationReadMethods(self, "spatial_autocorrelation")
        )
        self.geostat_cv_results: LocationReadMethods[GeostatCVResult] = LocationReadMethods(
            self, "geostat_cv_result"
        )
        self.sensor_network_designs: LocationReadMethods[SensorNetworkDesign] = LocationReadMethods(
            self, "sensor_network_design"
        )
        self.causal_loops: ReferenceReadMethods[CausalLoop] = ReferenceReadMethods(
            self, "causal_loop"
        )
        self.causal_links: CausalLinkReadMethods[CausalLink] = CausalLinkReadMethods(self)
        self.system_variables: LocationReadMethods[SystemVariable] = LocationReadMethods(
            self, "system_variable"
        )
        self.stock_flow_models: ReferenceReadMethods[StockFlowModel] = ReferenceReadMethods(
            self, "stock_flow_model"
        )
        self.stock_flow_runs: LocationReadMethods[StockFlowRun] = LocationReadMethods(
            self, "stock_flow_run"
        )
        self.system_archetypes: LocationReadMethods[SystemArchetype] = LocationReadMethods(
            self, "system_archetype"
        )
        self.leverage_assessments: LocationReadMethods[LeverageAssessment] = LocationReadMethods(
            self, "leverage_assessment"
        )
        self.time_delays: ReferenceReadMethods[TimeDelay] = ReferenceReadMethods(
            self, "time_delay"
        )
        self.structural_assumptions: LocationReadMethods[StructuralAssumption] = LocationReadMethods(
            self, "structural_assumption"
        )
        self.situation_assessments: LocationReadMethods[SituationAssessment] = LocationReadMethods(
            self, "situation_assessment"
        )
        self.assessment_signals: AssessmentChildReadMethods[AssessmentSignal] = (
            AssessmentChildReadMethods(self, "assessment_signal")
        )
        self.assessment_dimensions: AssessmentChildReadMethods[AssessmentDimension] = (
            AssessmentChildReadMethods(self, "assessment_dimension")
        )
        self.ooda_cycle_logs: LocationReadMethods[OodaCycleLog] = LocationReadMethods(
            self, "ooda_cycle_log"
        )
        self.crisp_risk_assessments: LocationReadMethods[CrispRiskAssessment] = LocationReadMethods(
            self, "crisp_risk_assessment"
        )
        self.crisp_carbon_yield_risks: AssessmentLocationReadMethods[CrispCarbonYieldRisk] = (
            AssessmentLocationReadMethods(self, "crisp_carbon_yield_risk")
        )
        self.crisp_climate_risks: AssessmentLocationReadMethods[CrispClimateRisk] = (
            AssessmentLocationReadMethods(self, "crisp_climate_risk")
        )
        self.crisp_policy_risks: AssessmentLocationReadMethods[CrispPolicyRisk] = (
            AssessmentLocationReadMethods(self, "crisp_policy_risk")
        )
        self.crisp_financial_risks: AssessmentLocationReadMethods[CrispFinancialRisk] = (
            AssessmentLocationReadMethods(self, "crisp_financial_risk")
        )
        self.crisp_implementation_risks: AssessmentLocationReadMethods[CrispImplementationRisk] = (
            AssessmentLocationReadMethods(self, "crisp_implementation_risk")
        )
        self.organic_certification_records: LocationReadMethods[OrganicCertificationRecord] = (
            LocationReadMethods(self, "organic_certification_record")
        )
        self.organic_transition_plans: LocationReadMethods[OrganicTransitionPlan] = (
            LocationReadMethods(self, "organic_transition_plan")
        )
        self.prohibited_substance_records: LocationReadMethods[ProhibitedSubstanceRecord] = (
            LocationReadMethods(self, "prohibited_substance_record")
        )
        self.buffer_zones: LocationReadMethods[BufferZone] = LocationReadMethods(self, "buffer_zone")
        self.organic_input_audits: LocationReadMethods[OrganicInputAudit] = LocationReadMethods(
            self, "organic_input_audit"
        )
        self.harvest_handling_records: LocationReadMethods[HarvestHandlingRecord] = (
            LocationReadMethods(self, "harvest_handling_record")
        )
        self.organic_compliance_checklists: LocationReadMethods[OrganicComplianceChecklist] = (
            LocationReadMethods(self, "organic_compliance_checklist")
        )
        self.organic_readiness_assessments: LocationReadMethods[OrganicReadinessAssessment] = (
            LocationReadMethods(self, "organic_readiness_assessment")
        )
        self.demand_forecasts: LocationReadMethods[DemandForecast] = LocationReadMethods(
            self, "demand_forecast"
        )
        self.market_size_estimates: LocationReadMethods[MarketSizeEstimate] = LocationReadMethods(
            self, "market_size_estimate"
        )
        self.price_observations: LocationReadMethods[PriceObservation] = LocationReadMethods(
            self, "price_observation"
        )
        self.demand_trends: LocationReadMethods[DemandTrend] = LocationReadMethods(
            self, "demand_trend"
        )
        self.buyer_demand_signals: LocationReadMethods[BuyerDemandSignal] = LocationReadMethods(
            self, "buyer_demand_signal"
        )
        self.production_market_matches: LocationReadMethods[ProductionMarketMatch] = LocationReadMethods(
            self, "production_market_match"
        )
        self.buyer_segments: LocationReadMethods[BuyerSegment] = LocationReadMethods(
            self, "buyer_segment"
        )
        self.value_flow_events: LocationReadMethods[ValueFlowEvent] = LocationReadMethods(
            self, "value_flow_event"
        )
        self.trend_estimates: LocationReadMethods[TrendEstimate] = LocationReadMethods(
            self, "trend_estimate"
        )
        self.trend_smoothing: LocationReadMethods[TrendSmoothing] = LocationReadMethods(
            self, "trend_smoothing"
        )
        self.change_points: LocationReadMethods[ChangePoint] = LocationReadMethods(
            self, "change_point"
        )
        self.seasonal_decompositions: LocationReadMethods[SeasonalDecomposition] = LocationReadMethods(
            self, "seasonal_decomposition"
        )
        self.trend_dashboard_metrics: LocationReadMethods[TrendDashboardMetric] = LocationReadMethods(
            self, "trend_dashboard_metric"
        )
        self.infrastructure_assets: LocationReadMethods[InfrastructureAsset] = LocationReadMethods(
            self, "infrastructure_asset"
        )
        self.farm_tasks: LocationReadMethods[FarmTask] = LocationReadMethods(self, "farm_task")
        self.crops: ReferenceReadMethods[Crop] = ReferenceReadMethods(self, "crop")
        self.protocols: ReferenceReadMethods[Protocol] = ReferenceReadMethods(self, "protocol")
        self.sensor_types: ReferenceReadMethods[SensorType] = ReferenceReadMethods(self, "sensor_type")
        self.attestation_schemas: ReferenceReadMethods[AttestationSchema] = ReferenceReadMethods(
            self, "attestation_schema"
        )

    # -- Auth ------------------------------------------------------------------

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate and store the bearer token on the session.

        Returns the full Directus auth response (access_token, refresh_token, etc.).
        """
        resp = self.session.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password},
        )
        self._handle_error(resp)
        body: Dict[str, Any] = resp.json().get("data", resp.json())
        access_token = body.get("access_token", body.get("token", ""))
        self.session.headers["Authorization"] = f"Bearer {access_token}"
        return body

    def logout(self) -> None:
        """Invalidate the current refresh token and clear local auth state."""
        try:
            self.session.post(f"{self.base_url}/auth/logout")
        except requests.RequestException:
            pass
        self.session.headers.pop("Authorization", None)

    # -- Generic CRUD ----------------------------------------------------------

    def list_items(
        self,
        collection: str,
        options: Optional[ListOptions] = None,
        **kwargs: Any,
    ) -> List[Any]:
        params = options.to_params() if options else {}
        params.update(kwargs)
        if params.get("offset") is not None:
            if params.get("limit") is None:
                # Match the TypeScript SDK and ListOptions contract: offset
                # pagination is meaningful only with a limit; page may still
                # be used when both forms are supplied without that limit.
                params.pop("offset")
            else:
                if params["limit"] == 0:
                    raise ValueError("offset pagination requires a non-zero limit")
                params.pop("page", None)
        resp = self.session.get(self._collection_url(collection), params=self._serialize_params(params))
        self._handle_error(resp)
        data = resp.json()
        return data.get("data", data)

    def get_item(self, collection: str, item_id: str, fields: Optional[List[str]] = None) -> Any:
        params: Dict[str, Any] = {}
        if fields is not None:
            # Match the pinned TypeScript Directus SDK's query shape: an empty
            # projection is sent as JSON `[]`, while populated fields are CSV.
            params["fields"] = json.dumps(fields) if not fields else ",".join(fields)
        resp = self.session.get(self._item_url(collection, item_id), params=params)
        self._handle_error(resp)
        data = resp.json()
        return data.get("data", data)

    def create_item(self, collection: str, data: Dict[str, Any]) -> Any:
        self._assert_generic_write_allowed(collection)
        resp = self.session.post(self._collection_url(collection), json=data)
        self._handle_error(resp)
        body = resp.json()
        return body.get("data", body)

    def create_items(self, collection: str, data: List[Dict[str, Any]]) -> List[Any]:
        self._assert_generic_write_allowed(collection)
        resp = self.session.post(self._collection_url(collection), json=data)
        self._handle_error(resp)
        body = resp.json()
        return body.get("data", body)

    def update_item(self, collection: str, item_id: str, data: Dict[str, Any]) -> Any:
        self._assert_generic_write_allowed(collection)
        resp = self.session.patch(self._item_url(collection, item_id), json=data)
        self._handle_error(resp)
        body = resp.json()
        return body.get("data", body)

    def delete_item(self, collection: str, item_id: str) -> None:
        self._assert_generic_write_allowed(collection)
        resp = self.session.delete(self._item_url(collection, item_id))
        self._handle_error(resp)

    @staticmethod
    def _assert_generic_write_allowed(collection: str) -> None:
        if collection in _READ_ONLY_PROJECTION_COLLECTIONS:
            raise ValidationError(
                f"Generic SDK mutations are disabled for read-only collection '{collection}'"
            )

    # -- Aggregate -------------------------------------------------------------

    def aggregate(self, collection: str, **kwargs: Any) -> List[Any]:
        """Run a Directus aggregate query through /items/:collection."""
        resp = self.session.get(
            self._collection_url(collection),
            params=self._serialize_params(kwargs),
        )
        self._handle_error(resp)
        data = resp.json()
        return data.get("data", data)

    # -- Internal helpers ------------------------------------------------------

    @staticmethod
    def _path_segment(value: str, name: str) -> str:
        """Encode a Directus route segment so caller data cannot change the URL path."""
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        if value in {"", ".", ".."}:
            raise ValueError(f"{name} must be a non-empty path segment")
        return quote(value, safe="")

    def _collection_url(self, collection: str) -> str:
        return f"{self.base_url}/items/{self._path_segment(collection, 'collection')}"

    def _item_url(self, collection: str, item_id: str) -> str:
        return f"{self._collection_url(collection)}/{self._path_segment(item_id, 'item_id')}"

    @staticmethod
    def _serialize_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """Encode nested objects as JSON and top-level arrays as Directus CSV."""
        out: Dict[str, Any] = {}
        for k, v in params.items():
            if isinstance(v, dict):
                out[k] = json.dumps(v)
            elif isinstance(v, list):
                out[k] = ",".join(str(item) for item in v)
            else:
                out[k] = v
        return out

    @staticmethod
    def _handle_error(resp: requests.Response) -> None:
        if resp.ok:
            return
        status = resp.status_code
        # Keep malformed-envelope behavior aligned with the JavaScript SDK.
        # Returning arbitrary response bodies here can also expose server detail
        # that is not part of the public error contract.
        message = f"HTTP {status}"
        try:
            body = resp.json()
        except ValueError:
            body = None

        if isinstance(body, dict):
            errors = body.get("errors")
            if isinstance(errors, list) and errors and isinstance(errors[0], dict):
                error_message = errors[0].get("message")
                if isinstance(error_message, str) and error_message:
                    message = error_message

        if status == 401:
            raise AuthenticationError(message, status, resp)
        if status == 403:
            raise ForbiddenError(message, status, resp)
        if status == 404:
            raise NotFoundError(message, status, resp)
        if status == 400:
            raise ValidationError(message, status, resp)
        raise KokonutError(message, status, resp)
