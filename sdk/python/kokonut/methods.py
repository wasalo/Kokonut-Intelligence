from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Generic, List, Optional, TypeVar

from .types import (
    AttestationRecord,
    CropCycle,
    ExpenseEvent,
    ExportLog,
    Farm,
    FieldNote,
    HarvestEvent,
    LaborEvent,
    ListOptions,
    Location,
    LossEvent,
    NoiSnapshot,
    Plot,
    ReportSnapshot,
    SalesEvent,
    SensorReading,
    WalletProfile,
)

if TYPE_CHECKING:
    from .client import KokonutClient


ReadModel = TypeVar("ReadModel")


def _to_dataclass(data: Dict[str, Any], cls: Any) -> Any:
    """Best-effort conversion of a dict to a dataclass, passing through unknown keys."""
    import dataclasses

    if not dataclasses.is_dataclass(cls):
        return data
    field_names = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in field_names}
    return cls(**filtered)


def _build_filter(*args: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for f in args:
        merged.update(f)
    merged.update(kwargs)
    return merged


def _list_options_with_filter(options: Optional[ListOptions], required_filter: Dict[str, Any]) -> ListOptions:
    """Preserve list options while making the convenience method's filter authoritative."""
    return ListOptions(
        filter=_build_filter(options.filter if options and options.filter else {}, required_filter),
        sort=options.sort if options else None,
        fields=options.fields if options else None,
        limit=options.limit if options else None,
        offset=options.offset if options else None,
        page=options.page if options else None,
        meta=options.meta if options else None,
    )


class GenericMethods:
    def __init__(self, client: KokonutClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    def list(self, options: Optional[ListOptions] = None, **kwargs: Any) -> List[Any]:
        return self._client.list_items(self._collection, options, **kwargs)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> Any:
        return self._client.get_item(self._collection, item_id, fields)

    def create(self, data: Dict[str, Any]) -> Any:
        return self._client.create_item(self._collection, data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[Any]:
        return self._client.create_items(self._collection, data)

    def update(self, item_id: str, data: Dict[str, Any]) -> Any:
        return self._client.update_item(self._collection, item_id, data)

    def delete(self, item_id: str) -> None:
        self._client.delete_item(self._collection, item_id)


class LocationReadMethods(Generic[ReadModel]):
    """Typed, location-scoped reads without generic mutation methods."""

    def __init__(self, client: KokonutClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    def list(self, options: Optional[ListOptions] = None) -> List[ReadModel]:
        return self._client.list_items(self._collection, options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> ReadModel:
        return self._client.get_item(self._collection, item_id, fields)

    def list_by_location(
        self, location_id: str, options: Optional[ListOptions] = None
    ) -> List[ReadModel]:
        return self._client.list_items(
            self._collection,
            _list_options_with_filter(options, {"location_id": {"_eq": location_id}}),
        )


class LocationMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "location")

    def list(self, options: Optional[ListOptions] = None) -> List[Location]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> Location:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> Location:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[Location]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> Location:
        return super().update(item_id, data)


class FarmMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "farm")

    def list(self, options: Optional[ListOptions] = None) -> List[Farm]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> Farm:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> Farm:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[Farm]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> Farm:
        return super().update(item_id, data)

    def list_by_location(self, location_id: str, options: Optional[ListOptions] = None) -> List[Farm]:
        return super().list(_list_options_with_filter(options, {"location_id": {"_eq": location_id}}))


class PlotMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "plot")

    def list(self, options: Optional[ListOptions] = None) -> List[Plot]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> Plot:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> Plot:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[Plot]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> Plot:
        return super().update(item_id, data)

    def list_by_farm(self, farm_id: str, options: Optional[ListOptions] = None) -> List[Plot]:
        return super().list(_list_options_with_filter(options, {"farm_id": {"_eq": farm_id}}))


class CropCycleMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "crop_cycle")

    def list(self, options: Optional[ListOptions] = None) -> List[CropCycle]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> CropCycle:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> CropCycle:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[CropCycle]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> CropCycle:
        return super().update(item_id, data)

    def list_by_plot(self, plot_id: str, options: Optional[ListOptions] = None) -> List[CropCycle]:
        return super().list(_list_options_with_filter(options, {"plot_id": {"_eq": plot_id}}))

    def list_active(self, options: Optional[ListOptions] = None) -> List[CropCycle]:
        return super().list(_list_options_with_filter(options, {"status": {"_in": ["planted", "growing"]}}))


class HarvestEventMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "harvest_event")

    def list(self, options: Optional[ListOptions] = None) -> List[HarvestEvent]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> HarvestEvent:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> HarvestEvent:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[HarvestEvent]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> HarvestEvent:
        return super().update(item_id, data)

    def list_by_crop_cycle(self, crop_cycle_id: str, options: Optional[ListOptions] = None) -> List[HarvestEvent]:
        return super().list(_list_options_with_filter(options, {"crop_cycle_id": {"_eq": crop_cycle_id}}))


class SalesEventMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "sales_event")

    def list(self, options: Optional[ListOptions] = None) -> List[SalesEvent]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> SalesEvent:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> SalesEvent:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[SalesEvent]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> SalesEvent:
        return super().update(item_id, data)

    def list_by_crop_cycle(self, crop_cycle_id: str, options: Optional[ListOptions] = None) -> List[SalesEvent]:
        return super().list(_list_options_with_filter(options, {"crop_cycle_id": {"_eq": crop_cycle_id}}))

    def list_unpaid(self, options: Optional[ListOptions] = None) -> List[SalesEvent]:
        return super().list(_list_options_with_filter(options, {"payment_status": {"_in": ["pending", "partial"]}}))


class ExpenseEventMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "expense_event")

    def list(self, options: Optional[ListOptions] = None) -> List[ExpenseEvent]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> ExpenseEvent:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> ExpenseEvent:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[ExpenseEvent]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> ExpenseEvent:
        return super().update(item_id, data)

    def list_by_crop_cycle(self, crop_cycle_id: str, options: Optional[ListOptions] = None) -> List[ExpenseEvent]:
        return super().list(_list_options_with_filter(options, {"crop_cycle_id": {"_eq": crop_cycle_id}}))

    def list_pending_approval(self, options: Optional[ListOptions] = None) -> List[ExpenseEvent]:
        return super().list(_list_options_with_filter(options, {"status": {"_eq": "submitted"}}))


class LossEventMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "loss_event")

    def list(self, options: Optional[ListOptions] = None) -> List[LossEvent]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> LossEvent:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> LossEvent:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[LossEvent]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> LossEvent:
        return super().update(item_id, data)

    def list_by_location(self, location_id: str, options: Optional[ListOptions] = None) -> List[LossEvent]:
        return super().list(_list_options_with_filter(options, {"location_id": {"_eq": location_id}}))


class LaborEventMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "labor_event")

    def list(self, options: Optional[ListOptions] = None) -> List[LaborEvent]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> LaborEvent:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> LaborEvent:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[LaborEvent]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> LaborEvent:
        return super().update(item_id, data)

    def list_by_location(self, location_id: str, options: Optional[ListOptions] = None) -> List[LaborEvent]:
        return super().list(_list_options_with_filter(options, {"location_id": {"_eq": location_id}}))


class FieldNoteMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "field_note")

    def list(self, options: Optional[ListOptions] = None) -> List[FieldNote]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> FieldNote:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> FieldNote:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[FieldNote]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> FieldNote:
        return super().update(item_id, data)

    def list_by_location(self, location_id: str, options: Optional[ListOptions] = None) -> List[FieldNote]:
        return super().list(_list_options_with_filter(options, {"location_id": {"_eq": location_id}}))


class SensorReadingMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "sensor_reading")

    def list(self, options: Optional[ListOptions] = None) -> List[SensorReading]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> SensorReading:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> SensorReading:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[SensorReading]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> SensorReading:
        return super().update(item_id, data)

    def list_by_device(self, sensor_id: str, options: Optional[ListOptions] = None) -> List[SensorReading]:
        return super().list(_list_options_with_filter(options, {"sensor_id": {"_eq": sensor_id}}))

    def list_by_plot(self, plot_id: str, options: Optional[ListOptions] = None) -> List[SensorReading]:
        return super().list(_list_options_with_filter(options, {"plot_id": {"_eq": plot_id}}))

    def list_anomalies(self, options: Optional[ListOptions] = None) -> List[SensorReading]:
        return super().list(_list_options_with_filter(options, {"quality": {"_eq": "suspect"}}))


class WalletProfileMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "wallet_profile")

    def list(self, options: Optional[ListOptions] = None) -> List[WalletProfile]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> WalletProfile:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> WalletProfile:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[WalletProfile]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> WalletProfile:
        return super().update(item_id, data)

    def find_by_address(self, address: str) -> Optional[WalletProfile]:
        results = self._client.list_items(
            "wallet_profile",
            ListOptions(filter={"address": {"_eq": address}}, limit=1),
        )
        return results[0] if results else None


class AttestationMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "attestation_record")

    def list(self, options: Optional[ListOptions] = None) -> List[AttestationRecord]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> AttestationRecord:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> AttestationRecord:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[AttestationRecord]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> AttestationRecord:
        return super().update(item_id, data)

    def list_pending(self, options: Optional[ListOptions] = None) -> List[AttestationRecord]:
        return super().list(_list_options_with_filter(options, {"status": {"_in": ["draft", "submitted"]}}))

    def list_by_entity(self, subject_type: str, subject_id: str) -> List[AttestationRecord]:
        return self._client.list_items(
            "attestation_record",
            ListOptions(filter={"subject_type": {"_eq": subject_type}, "subject_id": {"_eq": subject_id}}),
        )


class ReportMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "report_snapshot")

    def list(self, options: Optional[ListOptions] = None) -> List[ReportSnapshot]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> ReportSnapshot:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> ReportSnapshot:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[ReportSnapshot]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> ReportSnapshot:
        return super().update(item_id, data)

    def list_by_type(self, report_type: str, options: Optional[ListOptions] = None) -> List[ReportSnapshot]:
        return super().list(_list_options_with_filter(options, {"report_type": {"_eq": report_type}}))


class ExportMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "export_log")

    def list(self, options: Optional[ListOptions] = None) -> List[ExportLog]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> ExportLog:
        return super().get(item_id, fields)

    def create_export(
        self,
        export_type: str,
        format: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_ids: Optional[List[str]] = None,
        target_table: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> ExportLog:
        return super().create(
            {
                "export_type": export_type,
                "format": format,
                "entity_type": entity_type,
                "entity_ids": entity_ids,
                "target_table": target_table,
                "filters": filters,
                "status": "pending",
                "requested_by": "sdk",
            }
        )


class NoiMethods(GenericMethods):
    def __init__(self, client: KokonutClient) -> None:
        super().__init__(client, "noi_snapshot")

    def list(self, options: Optional[ListOptions] = None) -> List[NoiSnapshot]:
        return super().list(options)

    def get(self, item_id: str, fields: Optional[List[str]] = None) -> NoiSnapshot:
        return super().get(item_id, fields)

    def create(self, data: Dict[str, Any]) -> NoiSnapshot:
        return super().create(data)

    def create_many(self, data: List[Dict[str, Any]]) -> List[NoiSnapshot]:
        return super().create_many(data)

    def update(self, item_id: str, data: Dict[str, Any]) -> NoiSnapshot:
        return super().update(item_id, data)

    def list_by_crop_cycle(self, crop_cycle_id: str, options: Optional[ListOptions] = None) -> List[NoiSnapshot]:
        return super().list(_list_options_with_filter(options, {"crop_cycle_id": {"_eq": crop_cycle_id}}))
