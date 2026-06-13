-- ============================================================
-- 015_constraints.sql — CHECK constraints, updated_at trigger,
--                       UNIQUE indexes, FK indexes, ON DELETE SET NULL
-- ============================================================

-- ============================================================
-- 1. ENUM TYPES for CHECK constraints
-- ============================================================

DO $$ BEGIN
  CREATE TYPE lifecycle_status AS ENUM ('draft', 'submitted', 'verified', 'published', 'rejected');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE entity_status AS ENUM ('active', 'inactive', 'archived');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE entity_status_extended AS ENUM ('active', 'inactive', 'maintenance', 'decommissioned');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE payment_status_type AS ENUM ('pending', 'partial', 'paid', 'overdue', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE agent_execution_status AS ENUM ('queued', 'running', 'completed', 'failed', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE agent_review_status AS ENUM ('draft', 'submitted', 'verified', 'published', 'rejected');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE attestation_execution_status AS ENUM ('pending', 'submitted', 'confirmed', 'failed', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE agent_lifecycle AS ENUM ('active', 'paused', 'deregistered');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE sensor_severity AS ENUM ('info', 'warning', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE alert_lifecycle AS ENUM ('open', 'acknowledged', 'resolved', 'false_positive');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE wallet_tx_status AS ENUM ('success', 'failed', 'pending');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE indexer_status AS ENUM ('syncing', 'healthy', 'error', 'paused');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE ingestion_status AS ENUM ('success', 'failed', 'partial');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE migration_status AS ENUM ('applied', 'failed', 'rolled_back');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE export_status AS ENUM ('pending', 'generating', 'completed', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE job_status AS ENUM ('active', 'paused', 'error');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE governance_mechanism_type AS ENUM ('moloch_dao', 'guilds', 'multisig', 'cooperative');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE agent_action_result AS ENUM ('success', 'failed', 'skipped');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================
-- 2. ALTER TABLE to add CHECK constraints
-- ============================================================

-- --- Lifecycle status tables ---
ALTER TABLE farm_activity       DROP CONSTRAINT IF EXISTS chk_farm_activity_status;
ALTER TABLE farm_activity       ADD CONSTRAINT chk_farm_activity_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE harvest_event       DROP CONSTRAINT IF EXISTS chk_harvest_status;
ALTER TABLE harvest_event       ADD CONSTRAINT chk_harvest_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE sales_event         DROP CONSTRAINT IF EXISTS chk_sales_status;
ALTER TABLE sales_event         ADD CONSTRAINT chk_sales_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE expense_event       DROP CONSTRAINT IF EXISTS chk_expense_status;
ALTER TABLE expense_event       ADD CONSTRAINT chk_expense_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE loss_event          DROP CONSTRAINT IF EXISTS chk_loss_status;
ALTER TABLE loss_event          ADD CONSTRAINT chk_loss_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE labor_event         DROP CONSTRAINT IF EXISTS chk_labor_status;
ALTER TABLE labor_event         ADD CONSTRAINT chk_labor_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE field_note          DROP CONSTRAINT IF EXISTS chk_field_note_status;
ALTER TABLE field_note          ADD CONSTRAINT chk_field_note_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE mrv_claim           DROP CONSTRAINT IF EXISTS chk_mrv_claim_status;
ALTER TABLE mrv_claim           ADD CONSTRAINT chk_mrv_claim_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE attestation_record  DROP CONSTRAINT IF EXISTS chk_attestation_record_status;
ALTER TABLE attestation_record  ADD CONSTRAINT chk_attestation_record_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE forecast_scenario   DROP CONSTRAINT IF EXISTS chk_forecast_scenario_status;
ALTER TABLE forecast_scenario   ADD CONSTRAINT chk_forecast_scenario_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE report_snapshot     DROP CONSTRAINT IF EXISTS chk_report_snapshot_status;
ALTER TABLE report_snapshot     ADD CONSTRAINT chk_report_snapshot_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE dashboard_dataset   DROP CONSTRAINT IF EXISTS chk_dashboard_dataset_status;
ALTER TABLE dashboard_dataset   ADD CONSTRAINT chk_dashboard_dataset_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE ai_summary          DROP CONSTRAINT IF EXISTS chk_ai_summary_status;
ALTER TABLE ai_summary          ADD CONSTRAINT chk_ai_summary_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE farm_registry_record DROP CONSTRAINT IF EXISTS chk_farm_registry_status;
ALTER TABLE farm_registry_record ADD CONSTRAINT chk_farm_registry_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE inventory_event     DROP CONSTRAINT IF EXISTS chk_inventory_status;
ALTER TABLE inventory_event     ADD CONSTRAINT chk_inventory_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE maintenance_event   DROP CONSTRAINT IF EXISTS chk_maintenance_status;
ALTER TABLE maintenance_event   ADD CONSTRAINT chk_maintenance_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE revenue_event       DROP CONSTRAINT IF EXISTS chk_revenue_status;
ALTER TABLE revenue_event       ADD CONSTRAINT chk_revenue_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE mrv_event           DROP CONSTRAINT IF EXISTS chk_mrv_event_status;
ALTER TABLE mrv_event           ADD CONSTRAINT chk_mrv_event_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE attestation_request DROP CONSTRAINT IF EXISTS chk_attestation_request_status;
ALTER TABLE attestation_request ADD CONSTRAINT chk_attestation_request_status CHECK (status::lifecycle_status IS NOT NULL);

ALTER TABLE agent_task          DROP CONSTRAINT IF EXISTS chk_agent_task_review;
ALTER TABLE agent_task          ADD CONSTRAINT chk_agent_task_review CHECK (review_status::lifecycle_status IS NOT NULL);

-- --- Entity status tables ---
ALTER TABLE location            DROP CONSTRAINT IF EXISTS chk_location_status;
ALTER TABLE location            ADD CONSTRAINT chk_location_status CHECK (status::entity_status IS NOT NULL);

ALTER TABLE farm                DROP CONSTRAINT IF EXISTS chk_farm_status;
ALTER TABLE farm                ADD CONSTRAINT chk_farm_status CHECK (status::entity_status IS NOT NULL);

ALTER TABLE plot                DROP CONSTRAINT IF EXISTS chk_plot_status;
ALTER TABLE plot                ADD CONSTRAINT chk_plot_status CHECK (status::entity_status IS NOT NULL);

ALTER TABLE partner             DROP CONSTRAINT IF EXISTS chk_partner_status;
ALTER TABLE partner             ADD CONSTRAINT chk_partner_status CHECK (status::entity_status IS NOT NULL);

ALTER TABLE property            DROP CONSTRAINT IF EXISTS chk_property_status;
ALTER TABLE property            ADD CONSTRAINT chk_property_status CHECK (status::entity_status IS NOT NULL);

ALTER TABLE infrastructure_asset DROP CONSTRAINT IF EXISTS chk_infra_status;
ALTER TABLE infrastructure_asset ADD CONSTRAINT chk_infra_status CHECK (status::entity_status_extended IS NOT NULL);

ALTER TABLE capital_source      DROP CONSTRAINT IF EXISTS chk_capital_source_status;
ALTER TABLE capital_source      ADD CONSTRAINT chk_capital_source_status CHECK (status::entity_status IS NOT NULL);

ALTER TABLE sensor_device       DROP CONSTRAINT IF EXISTS chk_sensor_device_status;
ALTER TABLE sensor_device       ADD CONSTRAINT chk_sensor_device_status CHECK (status::entity_status_extended IS NOT NULL);

-- --- Payment status ---
ALTER TABLE sales_event         DROP CONSTRAINT IF EXISTS chk_sales_payment;
ALTER TABLE sales_event         ADD CONSTRAINT chk_sales_payment CHECK (payment_status::payment_status_type IS NOT NULL);

ALTER TABLE revenue_event       DROP CONSTRAINT IF EXISTS chk_revenue_payment;
ALTER TABLE revenue_event       ADD CONSTRAINT chk_revenue_payment CHECK (payment_status::payment_status_type IS NOT NULL);

-- --- Execution status ---
ALTER TABLE attestation_request DROP CONSTRAINT IF EXISTS chk_att_request_exec;
ALTER TABLE attestation_request ADD CONSTRAINT chk_att_request_exec CHECK (execution_status::attestation_execution_status IS NOT NULL);

ALTER TABLE agent_task          DROP CONSTRAINT IF EXISTS chk_agent_task_exec;
ALTER TABLE agent_task          ADD CONSTRAINT chk_agent_task_exec CHECK (execution_status::agent_execution_status IS NOT NULL);

ALTER TABLE agent_action_log    DROP CONSTRAINT IF EXISTS chk_agent_action_result;
ALTER TABLE agent_action_log    ADD CONSTRAINT chk_agent_action_result CHECK (action_result::agent_action_result IS NOT NULL);

-- --- Agent state ---
ALTER TABLE agent_identity      DROP CONSTRAINT IF EXISTS chk_agent_state;
ALTER TABLE agent_identity      ADD CONSTRAINT chk_agent_state CHECK (agent_state::agent_lifecycle IS NOT NULL);

-- --- Sensor severity & status ---
ALTER TABLE sensor_alert        DROP CONSTRAINT IF EXISTS chk_alert_severity;
ALTER TABLE sensor_alert        ADD CONSTRAINT chk_alert_severity CHECK (severity::sensor_severity IS NOT NULL);

ALTER TABLE sensor_alert        DROP CONSTRAINT IF EXISTS chk_alert_status;
ALTER TABLE sensor_alert        ADD CONSTRAINT chk_alert_status CHECK (status::alert_lifecycle IS NOT NULL);

-- --- Wallet status ---
ALTER TABLE wallet_activity_event DROP CONSTRAINT IF EXISTS chk_wallet_activity_status;
ALTER TABLE wallet_activity_event ADD CONSTRAINT chk_wallet_activity_status CHECK (status::wallet_tx_status IS NOT NULL);

-- --- Indexer status ---
ALTER TABLE chain_indexer_status DROP CONSTRAINT IF EXISTS chk_indexer_status;
ALTER TABLE chain_indexer_status ADD CONSTRAINT chk_indexer_status CHECK (status::indexer_status IS NOT NULL);

-- --- Governance status ---
ALTER TABLE ingestion_log       DROP CONSTRAINT IF EXISTS chk_ingestion_status;
ALTER TABLE ingestion_log       ADD CONSTRAINT chk_ingestion_status CHECK (status::ingestion_status IS NOT NULL);

ALTER TABLE schema_migration    DROP CONSTRAINT IF EXISTS chk_migration_status;
ALTER TABLE schema_migration    ADD CONSTRAINT chk_migration_status CHECK (status::migration_status IS NOT NULL);

ALTER TABLE export_log          DROP CONSTRAINT IF EXISTS chk_export_status;
ALTER TABLE export_log          ADD CONSTRAINT chk_export_status CHECK (status::export_status IS NOT NULL);

ALTER TABLE scheduled_job       DROP CONSTRAINT IF EXISTS chk_job_status;
ALTER TABLE scheduled_job       ADD CONSTRAINT chk_job_status CHECK (status::job_status IS NOT NULL);

-- ============================================================
-- 3. UNIQUE constraints (missing)
-- ============================================================

ALTER TABLE plot                ADD CONSTRAINT uq_plot_slug UNIQUE (slug);
ALTER TABLE attestation_record  ADD CONSTRAINT uq_attestation_record_uid UNIQUE (attestation_uid);
ALTER TABLE mrv_event           ADD CONSTRAINT uq_mrv_event_uid UNIQUE (attestation_uid);

-- ============================================================
-- 4. auto-update trigger for updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ DECLARE
  tbl TEXT;
BEGIN
  FOR tbl IN
    SELECT c.table_name
    FROM information_schema.columns c
    JOIN information_schema.tables t
      ON c.table_name = t.table_name AND c.table_schema = t.table_schema
    WHERE c.column_name = 'updated_at'
      AND c.table_schema = 'public'
      AND t.table_type = 'BASE TABLE'
  LOOP
    BEGIN
      EXECUTE format(
        'CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION set_updated_at()',
        tbl, tbl
      );
    EXCEPTION WHEN duplicate_object THEN
      NULL;
    END;
  END LOOP;
END $$;

-- ============================================================
-- 5. ON DELETE SET NULL for nullable FKs
-- ============================================================

-- 001_locations.sql
ALTER TABLE infrastructure_asset
  DROP CONSTRAINT IF EXISTS infrastructure_asset_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE staff
  DROP CONSTRAINT IF EXISTS staff_location_id_fkey,
  ADD FOREIGN KEY (location_id) REFERENCES location(id) ON DELETE SET NULL;

-- 003_operations.sql
ALTER TABLE farm_activity
  DROP CONSTRAINT IF EXISTS farm_activity_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE farm_activity
  DROP CONSTRAINT IF EXISTS farm_activity_crop_cycle_id_fkey,
  ADD FOREIGN KEY (crop_cycle_id) REFERENCES crop_cycle(id) ON DELETE SET NULL;

ALTER TABLE sales_event
  DROP CONSTRAINT IF EXISTS sales_event_harvest_id_fkey,
  ADD FOREIGN KEY (harvest_id) REFERENCES harvest_event(id) ON DELETE SET NULL;

ALTER TABLE sales_event
  DROP CONSTRAINT IF EXISTS sales_event_crop_cycle_id_fkey,
  ADD FOREIGN KEY (crop_cycle_id) REFERENCES crop_cycle(id) ON DELETE SET NULL;

ALTER TABLE sales_event
  DROP CONSTRAINT IF EXISTS sales_event_partner_id_fkey,
  ADD FOREIGN KEY (partner_id) REFERENCES partner(id) ON DELETE SET NULL;

ALTER TABLE expense_event
  DROP CONSTRAINT IF EXISTS expense_event_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE expense_event
  DROP CONSTRAINT IF EXISTS expense_event_crop_cycle_id_fkey,
  ADD FOREIGN KEY (crop_cycle_id) REFERENCES crop_cycle(id) ON DELETE SET NULL;

ALTER TABLE expense_event
  DROP CONSTRAINT IF EXISTS expense_event_vendor_id_fkey,
  ADD FOREIGN KEY (vendor_id) REFERENCES partner(id) ON DELETE SET NULL;

ALTER TABLE loss_event
  DROP CONSTRAINT IF EXISTS loss_event_crop_cycle_id_fkey,
  ADD FOREIGN KEY (crop_cycle_id) REFERENCES crop_cycle(id) ON DELETE SET NULL;

ALTER TABLE loss_event
  DROP CONSTRAINT IF EXISTS loss_event_harvest_id_fkey,
  ADD FOREIGN KEY (harvest_id) REFERENCES harvest_event(id) ON DELETE SET NULL;

ALTER TABLE loss_event
  DROP CONSTRAINT IF EXISTS loss_event_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE labor_event
  DROP CONSTRAINT IF EXISTS labor_event_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE labor_event
  DROP CONSTRAINT IF EXISTS labor_event_crop_cycle_id_fkey,
  ADD FOREIGN KEY (crop_cycle_id) REFERENCES crop_cycle(id) ON DELETE SET NULL;

ALTER TABLE labor_event
  DROP CONSTRAINT IF EXISTS labor_event_staff_id_fkey,
  ADD FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE SET NULL;

ALTER TABLE field_note
  DROP CONSTRAINT IF EXISTS field_note_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE field_note
  DROP CONSTRAINT IF EXISTS field_note_crop_cycle_id_fkey,
  ADD FOREIGN KEY (crop_cycle_id) REFERENCES crop_cycle(id) ON DELETE SET NULL;

-- 004_finance.sql
ALTER TABLE expense_category
  DROP CONSTRAINT IF EXISTS expense_category_parent_id_fkey,
  ADD FOREIGN KEY (parent_id) REFERENCES expense_category(id) ON DELETE SET NULL;

ALTER TABLE financial_transaction
  DROP CONSTRAINT IF EXISTS financial_transaction_capital_source_id_fkey,
  ADD FOREIGN KEY (capital_source_id) REFERENCES capital_source(id) ON DELETE SET NULL;

ALTER TABLE value_flow_event
  DROP CONSTRAINT IF EXISTS value_flow_event_location_id_fkey,
  ADD FOREIGN KEY (location_id) REFERENCES location(id) ON DELETE SET NULL;

ALTER TABLE excluded_value_event
  DROP CONSTRAINT IF EXISTS excluded_value_event_value_flow_id_fkey,
  ADD FOREIGN KEY (value_flow_id) REFERENCES value_flow_event(id) ON DELETE SET NULL;

-- 005_environmental.sql
ALTER TABLE soil_carbon_measurement
  DROP CONSTRAINT IF EXISTS soil_carbon_measurement_baseline_id_fkey,
  ADD FOREIGN KEY (baseline_id) REFERENCES soil_carbon_measurement(id) ON DELETE SET NULL;

ALTER TABLE species_observation
  DROP CONSTRAINT IF EXISTS species_observation_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE species_observation
  DROP CONSTRAINT IF EXISTS species_observation_observer_id_fkey,
  ADD FOREIGN KEY (observer_id) REFERENCES staff(id) ON DELETE SET NULL;

ALTER TABLE sensor_reading
  DROP CONSTRAINT IF EXISTS sensor_reading_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE environmental_baseline
  DROP CONSTRAINT IF EXISTS environmental_baseline_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE mrv_claim
  DROP CONSTRAINT IF EXISTS mrv_claim_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE mrv_claim
  DROP CONSTRAINT IF EXISTS mrv_claim_sensor_device_id_fkey,
  ADD FOREIGN KEY (sensor_device_id) REFERENCES sensor_device(id) ON DELETE SET NULL;

ALTER TABLE mrv_claim
  DROP CONSTRAINT IF EXISTS mrv_claim_sensor_alert_id_fkey,
  ADD FOREIGN KEY (sensor_alert_id) REFERENCES sensor_alert(id) ON DELETE SET NULL;

-- 006_web3.sql
ALTER TABLE dapp_session
  DROP CONSTRAINT IF EXISTS dapp_session_protocol_id_fkey,
  ADD FOREIGN KEY (protocol_id) REFERENCES protocol(id) ON DELETE SET NULL;

ALTER TABLE digital_lego_usage
  DROP CONSTRAINT IF EXISTS digital_lego_usage_wallet_id_fkey,
  ADD FOREIGN KEY (wallet_id) REFERENCES wallet_profile(id) ON DELETE SET NULL;

ALTER TABLE digital_lego_usage
  DROP CONSTRAINT IF EXISTS digital_lego_usage_location_id_fkey,
  ADD FOREIGN KEY (location_id) REFERENCES location(id) ON DELETE SET NULL;

ALTER TABLE governance_event
  DROP CONSTRAINT IF EXISTS governance_event_wallet_id_fkey,
  ADD FOREIGN KEY (wallet_id) REFERENCES wallet_profile(id) ON DELETE SET NULL;

ALTER TABLE governance_event
  DROP CONSTRAINT IF EXISTS governance_event_protocol_id_fkey,
  ADD FOREIGN KEY (protocol_id) REFERENCES protocol(id) ON DELETE SET NULL;

ALTER TABLE treasury_event
  DROP CONSTRAINT IF EXISTS treasury_event_location_id_fkey,
  ADD FOREIGN KEY (location_id) REFERENCES location(id) ON DELETE SET NULL;

ALTER TABLE treasury_event
  DROP CONSTRAINT IF EXISTS treasury_event_wallet_id_fkey,
  ADD FOREIGN KEY (wallet_id) REFERENCES wallet_profile(id) ON DELETE SET NULL;

-- 007_modeled_outputs.sql
ALTER TABLE forecast_scenario
  DROP CONSTRAINT IF EXISTS forecast_scenario_location_id_fkey,
  ADD FOREIGN KEY (location_id) REFERENCES location(id) ON DELETE SET NULL;

ALTER TABLE forecast_scenario
  DROP CONSTRAINT IF EXISTS forecast_scenario_parent_scenario_id_fkey,
  ADD FOREIGN KEY (parent_scenario_id) REFERENCES forecast_scenario(id) ON DELETE SET NULL;

ALTER TABLE forecast_output
  DROP CONSTRAINT IF EXISTS forecast_output_location_id_fkey,
  ADD FOREIGN KEY (location_id) REFERENCES location(id) ON DELETE SET NULL;

ALTER TABLE forecast_output
  DROP CONSTRAINT IF EXISTS forecast_output_crop_cycle_id_fkey,
  ADD FOREIGN KEY (crop_cycle_id) REFERENCES crop_cycle(id) ON DELETE SET NULL;

ALTER TABLE report_snapshot
  DROP CONSTRAINT IF EXISTS report_snapshot_location_id_fkey,
  ADD FOREIGN KEY (location_id) REFERENCES location(id) ON DELETE SET NULL;

ALTER TABLE dashboard_dataset
  DROP CONSTRAINT IF EXISTS dashboard_dataset_location_id_fkey,
  ADD FOREIGN KEY (location_id) REFERENCES location(id) ON DELETE SET NULL;

-- 008_governance.sql
ALTER TABLE api_key
  DROP CONSTRAINT IF EXISTS api_key_role_id_fkey,
  ADD FOREIGN KEY (role_id) REFERENCES app_role(id) ON DELETE SET NULL;

-- 011_sensor_registry.sql
ALTER TABLE sensor_device
  DROP CONSTRAINT IF EXISTS sensor_device_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE sensor_alert
  DROP CONSTRAINT IF EXISTS sensor_alert_reading_id_fkey,
  ADD FOREIGN KEY (reading_id) REFERENCES sensor_reading(id) ON DELETE SET NULL;

-- 013_prd_completion.sql
ALTER TABLE farm_registry_record
  DROP CONSTRAINT IF EXISTS farm_registry_record_farm_id_fkey,
  ADD FOREIGN KEY (farm_id) REFERENCES farm(id) ON DELETE SET NULL;

ALTER TABLE inventory_event
  DROP CONSTRAINT IF EXISTS inventory_event_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE inventory_event
  DROP CONSTRAINT IF EXISTS inventory_event_crop_cycle_id_fkey,
  ADD FOREIGN KEY (crop_cycle_id) REFERENCES crop_cycle(id) ON DELETE SET NULL;

ALTER TABLE maintenance_event
  DROP CONSTRAINT IF EXISTS maintenance_event_infrastructure_asset_id_fkey,
  ADD FOREIGN KEY (infrastructure_asset_id) REFERENCES infrastructure_asset(id) ON DELETE SET NULL;

ALTER TABLE maintenance_event
  DROP CONSTRAINT IF EXISTS maintenance_event_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE revenue_event
  DROP CONSTRAINT IF EXISTS revenue_event_crop_cycle_id_fkey,
  ADD FOREIGN KEY (crop_cycle_id) REFERENCES crop_cycle(id) ON DELETE SET NULL;

ALTER TABLE revenue_event
  DROP CONSTRAINT IF EXISTS revenue_event_partner_id_fkey,
  ADD FOREIGN KEY (partner_id) REFERENCES partner(id) ON DELETE SET NULL;

ALTER TABLE revenue_event
  DROP CONSTRAINT IF EXISTS revenue_event_capital_source_id_fkey,
  ADD FOREIGN KEY (capital_source_id) REFERENCES capital_source(id) ON DELETE SET NULL;

ALTER TABLE revenue_event
  DROP CONSTRAINT IF EXISTS revenue_event_sales_event_id_fkey,
  ADD FOREIGN KEY (sales_event_id) REFERENCES sales_event(id) ON DELETE SET NULL;

ALTER TABLE revenue_event
  DROP CONSTRAINT IF EXISTS revenue_event_financial_transaction_id_fkey,
  ADD FOREIGN KEY (financial_transaction_id) REFERENCES financial_transaction(id) ON DELETE SET NULL;

ALTER TABLE revenue_event
  DROP CONSTRAINT IF EXISTS revenue_event_treasury_event_id_fkey,
  ADD FOREIGN KEY (treasury_event_id) REFERENCES treasury_event(id) ON DELETE SET NULL;

ALTER TABLE revenue_event
  DROP CONSTRAINT IF EXISTS revenue_event_value_flow_id_fkey,
  ADD FOREIGN KEY (value_flow_id) REFERENCES value_flow_event(id) ON DELETE SET NULL;

ALTER TABLE mrv_event
  DROP CONSTRAINT IF EXISTS mrv_event_farm_registry_record_id_fkey,
  ADD FOREIGN KEY (farm_registry_record_id) REFERENCES farm_registry_record(id) ON DELETE SET NULL;

ALTER TABLE mrv_event
  DROP CONSTRAINT IF EXISTS mrv_event_plot_id_fkey,
  ADD FOREIGN KEY (plot_id) REFERENCES plot(id) ON DELETE SET NULL;

ALTER TABLE mrv_event
  DROP CONSTRAINT IF EXISTS mrv_event_crop_cycle_id_fkey,
  ADD FOREIGN KEY (crop_cycle_id) REFERENCES crop_cycle(id) ON DELETE SET NULL;

ALTER TABLE mrv_event
  DROP CONSTRAINT IF EXISTS mrv_event_mrv_claim_id_fkey,
  ADD FOREIGN KEY (mrv_claim_id) REFERENCES mrv_claim(id) ON DELETE SET NULL;

ALTER TABLE mrv_event
  DROP CONSTRAINT IF EXISTS mrv_event_attestation_record_id_fkey,
  ADD FOREIGN KEY (attestation_record_id) REFERENCES attestation_record(id) ON DELETE SET NULL;

ALTER TABLE attestation_request
  DROP CONSTRAINT IF EXISTS attestation_request_mrv_event_id_fkey,
  ADD FOREIGN KEY (mrv_event_id) REFERENCES mrv_event(id) ON DELETE SET NULL;

ALTER TABLE attestation_request
  DROP CONSTRAINT IF EXISTS attestation_request_mrv_claim_id_fkey,
  ADD FOREIGN KEY (mrv_claim_id) REFERENCES mrv_claim(id) ON DELETE SET NULL;

ALTER TABLE attestation_request
  DROP CONSTRAINT IF EXISTS attestation_request_report_snapshot_id_fkey,
  ADD FOREIGN KEY (report_snapshot_id) REFERENCES report_snapshot(id) ON DELETE SET NULL;

ALTER TABLE attestation_request
  DROP CONSTRAINT IF EXISTS attestation_request_value_flow_id_fkey,
  ADD FOREIGN KEY (value_flow_id) REFERENCES value_flow_event(id) ON DELETE SET NULL;

ALTER TABLE attestation_request
  DROP CONSTRAINT IF EXISTS attestation_request_schema_id_fkey,
  ADD FOREIGN KEY (schema_id) REFERENCES attestation_schema(id) ON DELETE SET NULL;

ALTER TABLE agent_task
  DROP CONSTRAINT IF EXISTS agent_task_attestation_request_id_fkey,
  ADD FOREIGN KEY (attestation_request_id) REFERENCES attestation_request(id) ON DELETE SET NULL;

-- ============================================================
-- 6. Missing FK indexes
-- ============================================================

-- 001
CREATE INDEX IF NOT EXISTS idx_infrastructure_asset_plot ON infrastructure_asset(plot_id);
CREATE INDEX IF NOT EXISTS idx_staff_location ON staff(location_id);

-- 003 (some already exist, add only missing ones)
CREATE INDEX IF NOT EXISTS idx_sales_event_partner ON sales_event(partner_id);
CREATE INDEX IF NOT EXISTS idx_expense_event_vendor ON expense_event(vendor_id);
CREATE INDEX IF NOT EXISTS idx_loss_event_harvest ON loss_event(harvest_id);
CREATE INDEX IF NOT EXISTS idx_loss_event_plot ON loss_event(plot_id);
CREATE INDEX IF NOT EXISTS idx_labor_event_plot ON labor_event(plot_id);
CREATE INDEX IF NOT EXISTS idx_labor_event_crop_cycle ON labor_event(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_labor_event_staff ON labor_event(staff_id);
CREATE INDEX IF NOT EXISTS idx_field_note_plot ON field_note(plot_id);
CREATE INDEX IF NOT EXISTS idx_field_note_crop_cycle ON field_note(crop_cycle_id);

-- 004
CREATE INDEX IF NOT EXISTS idx_expense_category_parent ON expense_category(parent_id);
CREATE INDEX IF NOT EXISTS idx_financial_transaction_capital_source ON financial_transaction(capital_source_id);
CREATE INDEX IF NOT EXISTS idx_value_flow_event_location ON value_flow_event(location_id);
CREATE INDEX IF NOT EXISTS idx_excluded_value_event_flow ON excluded_value_event(value_flow_id);

-- 005
CREATE INDEX IF NOT EXISTS idx_soil_carbon_location ON soil_carbon_measurement(location_id);
CREATE INDEX IF NOT EXISTS idx_soil_carbon_baseline ON soil_carbon_measurement(baseline_id);
CREATE INDEX IF NOT EXISTS idx_species_observation_observer ON species_observation(observer_id);
CREATE INDEX IF NOT EXISTS idx_remote_sensing_location ON remote_sensing_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_mrv_claim_plot ON mrv_claim(plot_id);
CREATE INDEX IF NOT EXISTS idx_verification_review_claim ON verification_review(claim_id);

-- 006
CREATE INDEX IF NOT EXISTS idx_dapp_session_wallet ON dapp_session(wallet_id);
CREATE INDEX IF NOT EXISTS idx_dapp_session_protocol ON dapp_session(protocol_id);
CREATE INDEX IF NOT EXISTS idx_governance_event_wallet ON governance_event(wallet_id);
CREATE INDEX IF NOT EXISTS idx_governance_event_protocol ON governance_event(protocol_id);
CREATE INDEX IF NOT EXISTS idx_treasury_event_wallet ON treasury_event(wallet_id);
CREATE INDEX IF NOT EXISTS idx_treasury_event_attestation ON treasury_event(attestation_uid);
CREATE INDEX IF NOT EXISTS idx_value_flow_event_attestation ON value_flow_event(attestation_uid);

-- 007
CREATE INDEX IF NOT EXISTS idx_forecast_scenario_location ON forecast_scenario(location_id);
CREATE INDEX IF NOT EXISTS idx_forecast_scenario_parent ON forecast_scenario(parent_scenario_id);
CREATE INDEX IF NOT EXISTS idx_forecast_output_crop_cycle ON forecast_output(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_dashboard_dataset_location ON dashboard_dataset(location_id);

-- 008
CREATE INDEX IF NOT EXISTS idx_api_key_role ON api_key(role_id);
CREATE INDEX IF NOT EXISTS idx_api_key_hash ON api_key(key_hash);

-- 013
CREATE INDEX IF NOT EXISTS idx_inventory_event_plot ON inventory_event(plot_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_event_asset ON maintenance_event(infrastructure_asset_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_event_plot ON maintenance_event(plot_id);
CREATE INDEX IF NOT EXISTS idx_revenue_event_partner ON revenue_event(partner_id);
CREATE INDEX IF NOT EXISTS idx_revenue_event_capital_source ON revenue_event(capital_source_id);
CREATE INDEX IF NOT EXISTS idx_revenue_event_sales ON revenue_event(sales_event_id);
CREATE INDEX IF NOT EXISTS idx_revenue_event_financial ON revenue_event(financial_transaction_id);
CREATE INDEX IF NOT EXISTS idx_revenue_event_treasury ON revenue_event(treasury_event_id);
CREATE INDEX IF NOT EXISTS idx_revenue_event_flow ON revenue_event(value_flow_id);
CREATE INDEX IF NOT EXISTS idx_revenue_event_payment_status ON revenue_event(payment_status);
CREATE INDEX IF NOT EXISTS idx_revenue_event_attestation ON revenue_event(attestation_uid);
CREATE INDEX IF NOT EXISTS idx_mrv_event_plot ON mrv_event(plot_id);
CREATE INDEX IF NOT EXISTS idx_mrv_event_crop_cycle ON mrv_event(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_mrv_event_claim ON mrv_event(mrv_claim_id);
CREATE INDEX IF NOT EXISTS idx_mrv_event_attestation_record ON mrv_event(attestation_record_id);
CREATE INDEX IF NOT EXISTS idx_attestation_request_mrv_event ON attestation_request(mrv_event_id);
CREATE INDEX IF NOT EXISTS idx_attestation_request_mrv_claim ON attestation_request(mrv_claim_id);
CREATE INDEX IF NOT EXISTS idx_attestation_request_report ON attestation_request(report_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_attestation_request_flow ON attestation_request(value_flow_id);
CREATE INDEX IF NOT EXISTS idx_attestation_request_schema ON attestation_request(schema_id);
CREATE INDEX IF NOT EXISTS idx_agent_task_request ON agent_task(attestation_request_id);
CREATE INDEX IF NOT EXISTS idx_agent_identity_wallet ON agent_identity(operator_wallet);

-- ============================================================
-- 7. Data integrity comment
-- ============================================================

COMMENT ON COLUMN attestation_record.claim_data IS
  'Public attestation claims only. Private evidence must NOT be stored here — use private_payload_hash and payload_cid instead.';
