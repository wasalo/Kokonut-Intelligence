"""Canonical ingestion producers enqueue ClickHouse delivery."""

from unittest.mock import MagicMock, patch


def test_weather_queues_instead_of_inserting():
    from services.ingestion.weather import insert_weather_clickhouse

    record = {"location_id": "loc", "observation_date": "2026-01-01", "observation_time": "12:00:00"}
    with patch("services.ingestion.weather.enqueue") as queue, patch("services.ingestion.weather.insert_clickhouse_rows") as direct:
        insert_weather_clickhouse([record], MagicMock())
    queue.assert_called_once()
    direct.assert_not_called()


def test_forecast_queues_instead_of_inserting():
    from services.ingestion.weather_forecast import insert_forecasts_clickhouse

    record = {"location_id": "loc", "forecast_date": "2026-01-01", "forecast_hour": 12}
    with patch("services.ingestion.weather_forecast.enqueue") as queue, patch("services.ingestion.weather_forecast.insert_clickhouse_rows") as direct:
        insert_forecasts_clickhouse([record], MagicMock())
    queue.assert_called_once()
    direct.assert_not_called()


def test_sensor_queues_instead_of_inserting():
    from services.ingestion.sensor_ingester import insert_reading_clickhouse

    info = ("sensor", "name", "slug", "type-id", "soil_moisture", "loc", None, "active", "http")
    with patch("services.ingestion.sensor_ingester.enqueue") as queue, patch("services.ingestion.sensor_ingester.insert_clickhouse_rows") as direct:
        insert_reading_clickhouse(info, "2026-01-01", "12:00:00", 20.0, conn=MagicMock())
    queue.assert_called_once()
    direct.assert_not_called()


def test_remote_sensing_queues_instead_of_inserting():
    from services.ingestion.remote_sensing import insert_clickhouse

    record = {"id": "11111111-1111-1111-1111-111111111111", "location_id": "22222222-2222-2222-2222-222222222222", "plot_id": "33333333-3333-3333-3333-333333333333", "observation_date": "2026-01-01", "source": "manual"}
    with patch("services.ingestion.remote_sensing.enqueue") as queue, patch("services.ingestion.remote_sensing.post_clickhouse_rows") as direct:
        insert_clickhouse(record, MagicMock())
    queue.assert_called_once()
    direct.assert_not_called()


def test_remote_sensing_api_adapters_queue_instead_of_inserting():
    record = {"id": "obs", "location_id": "loc", "plot_id": None,
              "observation_date": "2026-01-01", "source": "sentinel-2"}
    import services.ingestion.gee_remote_sensing
    with patch("services.ingestion.gee_remote_sensing.enqueue") as gee_queue, patch("services.ingestion.gee_remote_sensing.post_clickhouse_rows") as gee_direct:
        from services.ingestion.gee_remote_sensing import _insert_ch as gee_insert
        gee_insert(record, MagicMock())
    gee_queue.assert_called_once()
    gee_direct.assert_not_called()

    import services.ingestion.copernicus_remote_sensing
    with patch("services.ingestion.copernicus_remote_sensing.enqueue") as copernicus_queue, patch("services.ingestion.copernicus_remote_sensing.post_clickhouse_rows") as copernicus_direct:
        from services.ingestion.copernicus_remote_sensing import _insert_ch as copernicus_insert
        copernicus_insert(record, MagicMock())
    copernicus_queue.assert_called_once()
    copernicus_direct.assert_not_called()


def test_attestation_producers_queue_instead_of_inserting():
    att = {"id": "uid", "schema": {"id": "schema"}, "blockTimestamp": "1", "time": "1"}
    import services.ingestion.subgraph_indexer
    with patch("services.ingestion.subgraph_indexer.enqueue") as subgraph_queue, patch("services.ingestion.subgraph_indexer.post_clickhouse_rows") as subgraph_direct:
        from services.ingestion.subgraph_indexer import insert_clickhouse
        insert_clickhouse("celo", att, "published", MagicMock())
    subgraph_queue.assert_called_once()
    subgraph_direct.assert_not_called()

    import services.ingestion.eas_indexer
    with patch("services.ingestion.eas_indexer.enqueue") as eas_queue, patch("services.ingestion.eas_indexer.post_clickhouse_rows") as eas_direct:
        from services.ingestion.eas_indexer import insert_clickhouse as eas_insert
        eas_insert("celo", {"id": "uid", "schema": {"id": "schema"}, "time": "1"}, "published", MagicMock())
    eas_queue.assert_called_once()
    eas_direct.assert_not_called()


def test_gnosis_producers_queue_instead_of_inserting():
    record = {"usage_date": "2026-01-01", "chain": "gnosis", "tx_hash": "0xabc",
              "action_type": "vote", "event_type": "vote_cast", "block_timestamp": "2026-01-01T00:00:00+00:00"}
    import services.ingestion.gnosis_indexer
    with patch("services.ingestion.gnosis_indexer.enqueue") as queue, patch("services.ingestion.gnosis_indexer.post_clickhouse_rows") as direct:
        from services.ingestion.gnosis_indexer import insert_dlego_clickhouse, insert_activity_clickhouse
        insert_dlego_clickhouse(record, MagicMock())
        insert_activity_clickhouse(record, MagicMock())
    assert queue.call_count == 2
    direct.assert_not_called()


def test_sensor_transport_helpers_queue_instead_of_inserting():
    import services.ingestion.http_sensor_receiver
    with patch("services.ingestion.http_sensor_receiver.enqueue") as http_queue, patch("services.ingestion.http_sensor_receiver.post_clickhouse_rows") as http_direct:
        from services.ingestion.http_sensor_receiver import _insert_ch
        _insert_ch("reading", "loc", None, "sensor", "soil_moisture", 20, "%", "2026-01-01T00:00:00Z", conn=MagicMock())
    http_queue.assert_called_once()
    http_direct.assert_not_called()

    import services.ingestion.mqtt_subscriber
    with patch("services.ingestion.mqtt_subscriber.enqueue") as mqtt_queue, patch("services.ingestion.mqtt_subscriber.post_clickhouse_rows") as mqtt_direct:
        from services.ingestion.mqtt_subscriber import MQTTSensorSubscriber
        MQTTSensorSubscriber()._insert_ch("reading", "loc", None, "sensor", "soil_moisture", 20, "%", "2026-01-01T00:00:00Z", conn=MagicMock())
    mqtt_queue.assert_called_once()
    mqtt_direct.assert_not_called()
