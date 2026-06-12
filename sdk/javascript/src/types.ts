export interface Location {
  id: string;
  name: string;
  slug: string;
  description?: string;
  boundary?: Record<string, any>;
  baseline_revenue?: number;
  baseline_asset_value?: number;
  baseline_cash_flow?: number;
  status: 'active' | 'inactive' | 'archived';
  created_at: string;
  updated_at: string;
}

export interface Farm {
  id: string;
  location_id: string;
  name: string;
  farm_type: 'operational' | 'nursery' | 'processing' | 'storage';
  total_area: number;
  area_unit: 'ha' | 'acres' | 'm2';
  status: 'active' | 'inactive';
  created_at: string;
  updated_at: string;
}

export interface Plot {
  id: string;
  farm_id: string;
  name: string;
  area: number;
  area_unit: 'ha' | 'acres' | 'm2';
  soil_type?: string;
  water_source?: string;
  boundary?: Record<string, any>;
  status: 'active' | 'fallow' | 'retired';
  created_at: string;
  updated_at: string;
}

export interface CropCycle {
  id: string;
  plot_id: string;
  crop_id: string;
  cycle_name: string;
  planting_date: string;
  expected_harvest_date?: string;
  actual_harvest_date?: string;
  status: 'planned' | 'planted' | 'growing' | 'harvested' | 'completed' | 'cancelled';
  yield_target?: number;
  yield_actual?: number;
  yield_unit?: string;
  created_at: string;
  updated_at: string;
}

export interface HarvestEvent {
  id: string;
  crop_cycle_id: string;
  plot_id: string;
  harvest_date: string;
  quantity: number;
  unit: string;
  quality_grade?: string;
  gross_weight?: number;
  net_weight?: number;
  loss_quantity?: number;
  loss_reason?: string;
  status: 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
  recorded_by?: string;
  created_at: string;
  updated_at: string;
}

export interface SalesEvent {
  id: string;
  crop_cycle_id: string;
  harvest_event_id?: string;
  buyer_id?: string;
  buyer_name: string;
  sale_date: string;
  quantity: number;
  unit: string;
  price_per_unit: number;
  total_amount: number;
  currency: string;
  payment_status: 'pending' | 'partial' | 'paid' | 'overdue' | 'cancelled';
  status: 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
  created_at: string;
  updated_at: string;
}

export interface ExpenseEvent {
  id: string;
  crop_cycle_id?: string;
  plot_id?: string;
  location_id?: string;
  category: string;
  description: string;
  amount: number;
  currency: string;
  vendor?: string;
  allocation_method: 'direct' | 'proportional' | 'equal';
  receipt_url?: string;
  expense_date: string;
  status: 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
  recorded_by?: string;
  created_at: string;
  updated_at: string;
}

export interface SensorReading {
  id: string;
  sensor_id: string;
  crop_cycle_id?: string;
  plot_id?: string;
  reading_date: string;
  value: number;
  unit: string;
  quality: 'good' | 'suspect' | 'bad';
  anomaly_flag: boolean;
  anomaly_score?: number;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface WalletProfile {
  id: string;
  address: string;
  chain: string;
  role: 'farm' | 'buyer' | 'investor' | 'verifier' | 'community' | 'treasury';
  owner_type?: string;
  owner_id?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AttestationRecord {
  id: string;
  attestation_uid?: string;
  schema_id?: string;
  entity_type: string;
  entity_id: string;
  claim_type: string;
  claim_data: Record<string, any>;
  evidence_hashes?: string[];
  status: 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
  reviewer_id?: string;
  review_notes?: string;
  chain?: string;
  attested_at?: string;
  expires_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ReportSnapshot {
  id: string;
  report_type: string;
  entity_type?: string;
  entity_id?: string;
  report_data: Record<string, any>;
  snapshot_hash: string;
  generated_by: string;
  period_start?: string;
  period_end?: string;
  status: 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
  created_at: string;
}

export interface ExportLog {
  id: string;
  export_type: string;
  format: 'csv' | 'json' | 'xlsx' | 'pdf' | 'parquet';
  entity_type?: string;
  entity_ids?: string[];
  filters?: Record<string, any>;
  file_path?: string;
  file_size?: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  requested_by: string;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface ListOptions {
  filter?: Record<string, any>;
  sort?: string[];
  fields?: string[];
  limit?: number;
  offset?: number;
  page?: number;
  meta?: 'total_count' | 'filter_count';
}

export interface WorkflowState {
  entity_type: string;
  entity_id: string;
  from_state: string;
  to_state: string;
  changed_by: string;
  notes?: string;
}
