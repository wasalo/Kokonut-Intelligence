-- ============================================================
-- 119_driver_registry.sql — Plugin architecture for data sources
-- ============================================================
-- Driver registry enables adding new data sources without modifying
-- core code. Drivers implement the DataSourceDriver protocol and are
-- discovered/loaded dynamically.

CREATE TABLE IF NOT EXISTS driver_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_name VARCHAR(100) NOT NULL UNIQUE,
    driver_version VARCHAR(20) NOT NULL,
    driver_type VARCHAR(50) NOT NULL
        CHECK (driver_type IN ('sensor', 'remote_sensing', 'market', 'blockchain', 'weather', 'climate', 'gis')),
    module_path VARCHAR(200) NOT NULL,
    class_name VARCHAR(100) NOT NULL DEFAULT 'Driver',
    config_schema JSONB,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    author VARCHAR(100),
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_driver_registry_type
    ON driver_registry (driver_type, is_enabled);
CREATE INDEX IF NOT EXISTS idx_driver_registry_name
    ON driver_registry (driver_name);

CREATE TABLE IF NOT EXISTS driver_instance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id UUID NOT NULL REFERENCES driver_registry(id) ON DELETE CASCADE,
    instance_name VARCHAR(100) NOT NULL UNIQUE,
    config JSONB NOT NULL DEFAULT '{}',
    location_id UUID,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    last_status VARCHAR(20)
        CHECK (last_status IN ('success', 'failed', 'running', 'disabled')),
    last_error TEXT,
    run_count INTEGER NOT NULL DEFAULT 0,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_driver_instance_driver
    ON driver_instance (driver_id, is_enabled);
CREATE INDEX IF NOT EXISTS idx_driver_instance_location
    ON driver_instance (location_id) WHERE location_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS driver_instance_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id UUID NOT NULL REFERENCES driver_instance(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('success', 'failed', 'timeout')),
    records_fetched INTEGER DEFAULT 0,
    records_written INTEGER DEFAULT 0,
    duration_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_driver_instance_log_instance
    ON driver_instance_log (instance_id, created_at DESC);

-- Seed built-in drivers from existing ingestion modules
INSERT INTO driver_registry (driver_name, driver_version, driver_type, module_path, class_name, author, description) VALUES
    ('weather_openweathermap', '1.0.0', 'weather', 'services.ingestion.drivers.weather_openweathermap', 'Driver', 'Kokonut', 'OpenWeatherMap current weather ingestion'),
    ('sensor_csv', '1.0.0', 'sensor', 'services.ingestion.drivers.sensor_csv', 'Driver', 'Kokonut', 'CSV batch sensor data ingestion'),
    ('sensor_mqtt', '1.0.0', 'sensor', 'services.ingestion.drivers.sensor_mqtt', 'Driver', 'Kokonut', 'MQTT real-time sensor ingestion'),
    ('remote_sensing_gee', '1.0.0', 'remote_sensing', 'services.ingestion.drivers.remote_sensing_gee', 'Driver', 'Kokonut', 'Google Earth Engine remote sensing'),
    ('remote_sensing_copernicus', '1.0.0', 'remote_sensing', 'services.ingestion.drivers.remote_sensing_copernicus', 'Driver', 'Kokonut', 'Copernicus Data Space remote sensing'),
    ('market_worldbank', '1.0.0', 'market', 'services.ingestion.drivers.market_worldbank', 'Driver', 'Kokonut', 'World Bank Pink Sheet commodity prices'),
    ('blockchain_eas', '1.0.0', 'blockchain', 'services.ingestion.drivers.blockchain_eas', 'Driver', 'Kokonut', 'EAS attestation indexer'),
    ('blockchain_rpc', '1.0.0', 'blockchain', 'services.ingestion.drivers.blockchain_rpc', 'Driver', 'Kokonut', 'RPC wallet activity indexer'),
    ('blockchain_gnosis', '1.0.0', 'blockchain', 'services.ingestion.drivers.blockchain_gnosis', 'Driver', 'Kokonut', 'Gnosis Chain Moloch DAO indexer')
ON CONFLICT (driver_name) DO UPDATE SET
    driver_version = EXCLUDED.driver_version,
    module_path = EXCLUDED.module_path,
    class_name = EXCLUDED.class_name,
    description = EXCLUDED.description,
    updated_at = NOW();
