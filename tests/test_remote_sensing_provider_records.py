"""Remote-sensing provider adapters expose database-free normalized results."""

from unittest.mock import MagicMock, patch

LOCATION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


class _EarthEngine:
    class Geometry:
        @staticmethod
        def Rectangle(_coordinates):
            return MagicMock(centroid=MagicMock(return_value="centroid"))

    class Filter:
        @staticmethod
        def lt(_field, _value):
            return "cloud-filter"

    @staticmethod
    def ImageCollection(_name):
        collection = MagicMock()
        collection.filterBounds.return_value = collection
        collection.filterDate.return_value = collection
        collection.filter.return_value = collection
        collection.size.return_value.getInfo.return_value = 1
        composite = MagicMock()
        composite.sampleRegion.return_value.getInfo.return_value = {
            "features": [{"properties": {"B2": 0.05, "B3": 0.1, "B4": 0.1, "B8": 0.4}}]
        }
        collection.median.return_value = composite
        return collection

    @staticmethod
    def FeatureCollection(_features):
        return "features"

    @staticmethod
    def Feature(_geometry):
        return "feature"


def test_gee_record_fetch_normalizes_without_a_database_connection():
    from services.ingestion.gee_remote_sensing import fetch_gee_records

    job = {
        "id": "job-1",
        "location_id": LOCATION_ID,
        "plot_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "cadence_days": 7,
        "cloud_max_pct": 20,
        "_resolved_bbox": {"west": -70.0, "south": 18.0, "east": -69.0, "north": 19.0},
    }
    with patch("services.ingestion.gee_remote_sensing._get_gee_client", return_value=_EarthEngine):
        result, records = fetch_gee_records(job)

    assert result["status"] == "success"
    assert result["observations"] == 1
    assert records[0]["location_id"] == LOCATION_ID
    assert records[0]["source_system"] == "gee_api"
    assert records[0]["ndvi"] is not None


def test_copernicus_record_fetch_normalizes_without_persisting():
    from services.ingestion.copernicus_remote_sensing import fetch_copernicus_records

    response = MagicMock()
    response.json.return_value = {
        "value": [{
            "Id": "product-1",
            "Name": "synthetic-scene",
            "Attributes": [{"Name": "cloudCover", "Value": 12.5}],
        }]
    }
    job = {
        "id": "job-1",
        "location_id": LOCATION_ID,
        "plot_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "cadence_days": 7,
        "cloud_max_pct": 20,
        "_resolved_bbox": {"west": -70.0, "south": 18.0, "east": -69.0, "north": 19.0},
    }
    with (
        patch("services.ingestion.copernicus_remote_sensing._get_token", return_value="synthetic-token"),
        patch("services.ingestion.copernicus_remote_sensing.http.get", return_value=response),
    ):
        result, records = fetch_copernicus_records(job)

    assert result["status"] == "success"
    assert result["observations"] == 1
    assert records[0]["location_id"] == LOCATION_ID
    assert records[0]["source_system"] == "copernicus_api"
    assert records[0]["source_id"] == "product-1"
    assert records[0]["cloud_cover_pct"] == 12.5
